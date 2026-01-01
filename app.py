import os
import asyncio
import json
from pathlib import Path
from openai import OpenAI
from flask import Flask, request, render_template, jsonify
from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any, List
from dotenv import load_dotenv
from datetime import datetime
from agents.scraper import UniversalJobScraperV73
from agents.emailer import send_email_with_resume
# 🔥 FIXED IMPORT: Use ResumeParserV2 class
from agents.parser import ResumeParserV2  # ← CHANGED: Import CLASS not functions


# 🔥 FIREBASE (Optional)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_OK = True
except ImportError:
    FIREBASE_OK = False


load_dotenv()
app = Flask(__name__)


# 🔥 GROQ SETUP
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env")


client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
print(f"✅ Groq client ready - Model: groq/compound")


# 🔥 Firebase Setup
db = None
if FIREBASE_OK:
    try:
        if os.path.exists("firebase.json"):
            cred = credentials.Certificate("firebase.json")
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("✅ Firebase connected!")
    except Exception as e:
        print(f"⚠️ Firebase error: {e}")


class AgentState(TypedDict):
    resume_data: Dict[str, Any]
    jobs_data: Dict[str, Any]
    analysis: Dict[str, Any]
    company_url: str
    user_id: str


# 🔥 AGENT 1: Resume Parser (UPDATED - Uses ResumeParserV2)
async def agent_parse_resume(state: AgentState) -> AgentState:
    print("🔍 Agent 1: Parsing resume...")
    resume_path = "data/resume/resume.pdf"
    os.makedirs(os.path.dirname(resume_path), exist_ok=True)
    
    # 🔥 FIXED: Use ResumeParserV2 class instance
    parser = ResumeParserV2()
    raw_text = parser.extract_text(resume_path)
    state["resume_data"] = parser.extract_basic_info(raw_text)
    print(f"✅ Resume: {state['resume_data'].get('name', 'Unknown')} - {len(state['resume_data'].get('skills_flat', []))} skills")
    return state


# 🔥 AGENT 2: V7.3 Scraper
async def agent_scrape_jobs(state: AgentState) -> AgentState:
    print(f"🌐 Agent 2: V7.3 scraping {state['company_url']}...")
    scraper = UniversalJobScraperV73("data/company")
    state["jobs_data"] = await scraper.scrape_single_url(state["company_url"])
    jobs_count = len(state["jobs_data"].get("jobs", []))
    pages_scraped = state["jobs_data"].get("scraping_metadata", {}).get("pages_scraped", 0)
    print(f"✅ V7.3: {jobs_count}/15 jobs | Pages: {pages_scraped}")
    return state


# 🔥 AGENT 3: GROQ Analysis
async def agent_analyze_groq(state: AgentState) -> AgentState:
    print("🧠 Agent 3: Groq 'groq/compound' analyzing...")
    
    resume_text = state["resume_data"].get("raw_text", "")[:3000]
    skills_resume = state["resume_data"].get("skills_flat", [])  # ← FIXED: Use skills_flat
    
    jobs_v73 = state["jobs_data"].get("jobs", [])
    
    jobs_summary = []
    for job in jobs_v73[:8]:
        jobs_summary.append({
            "title": job["title"][:80],
            "location": job["location"].get("city", "Unknown"),
            "seniority": job.get("seniority_level", "Mid"),
            "skills": job.get("skills", {}),
            "url": job["application"]["apply_url"]
        })
    
    prompt = f"""
You are a job matching expert. Analyze this resume against V7.3 scraped jobs.

RESUME SKILLS: {skills_resume}
RESUME TEXT: {resume_text[:1000]}

JOBS (top 8):
{jobs_summary}

Return ONLY valid JSON (no explanations):
{{
  "jobs": [
    {{
      "title": "exact job title",
      "match_score": 92,
      "match_percentage": "92%",
      "improvements": ["Add AWS projects", "Quantify Python experience"],
      "why_good_fit": "Python skills match + Pune location perfect",
      "apply_url": "exact URL",
      "priority": "HIGH",
      "skills_match": {{"programming": 4, "cloud": 2}}
    }}
  ]
}}

Rules:
- Pune/India jobs = +20% bonus, HIGH priority
- Scores: 70-95% based on skills/location match
- JSON ONLY - no other text
"""
    
    try:
        response = client.chat.completions.create(
            model="groq/compound",
            messages=[
                {"role": "system", "content": "You are a precise job matching AI. Always return clean JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000,
            tool_choice="none"
        )
        
        groq_output = response.choices[0].message.content.strip()
        print(f"Groq raw: {groq_output[:200]}...")
        
        try:
            state["analysis"] = json.loads(groq_output)
            if not isinstance(state["analysis"].get("jobs"), list):
                raise ValueError("Invalid JSON structure")
            print(f"✅ Groq analyzed {len(state['analysis']['jobs'])} jobs")
        except Exception as parse_error:
            print(f"Groq JSON parse failed: {parse_error}")
            state["analysis"] = create_fallback_analysis(jobs_v73, skills_resume)
            
    except Exception as groq_error:
        print(f"Groq error: {groq_error} - using fallback")
        state["analysis"] = create_fallback_analysis(jobs_v73, skills_resume)
    
    return state


# 🔥 FALLBACK ANALYSIS
def create_fallback_analysis(jobs_v73: List[Dict], skills_resume: List[str]) -> List[Dict]:
    analyzed_jobs = []
    for i, job in enumerate(jobs_v73[:10]):
        job_skills = job.get("skills", {})
        skill_score = sum(job_skills.values()) if job_skills else 0
        location_bonus = 20 if any(x in str(job["location"]).lower() for x in ["pune", "india"]) else 0
        match_score = min(95, 70 + skill_score * 3 + location_bonus)
        
        top_skill = list(job_skills.keys())[0] if job_skills else "relevant projects"
        
        analyzed_jobs.append({
            "title": job["title"][:70],
            "match_score": match_score,
            "match_percentage": f"{match_score}%",
            "improvements": [
                f"Highlight {top_skill} experience",
                "Add quantifiable achievements",
                f"Tailor for {job.get('seniority_level', 'Mid-level')} role"
            ],
            "why_good_fit": f"{job['location'].get('city', 'Remote')} + {job.get('seniority_level', 'Mid')} match",
            "apply_url": job["application"]["apply_url"],
            "priority": "HIGH" if location_bonus > 0 else "MEDIUM",
            "skills_match": job_skills
        })
    return {"jobs": analyzed_jobs}


# 🔥 ROUTER
def should_send_email(state: AgentState) -> str:
    high_matches = sum(1 for j in state.get("analysis", {}).get("jobs", []) if j.get("match_score", 0) >= 80)
    if high_matches < 3:
        print(f"📧 Low matches ({high_matches}/3) → Email ready")
        return "email"
    print(f"✅ {high_matches} good matches → Skip email")
    return END


# 🔥 AGENT 4: Email Prep
async def agent_send_email(state: AgentState) -> AgentState:
    print("📧 Agent 4: Cold email prepared...")
    company_email = state["jobs_data"].get("contact_information", {}).get("privacy_email", "")
    if company_email:
        state["analysis"]["cold_email"] = {
            "ready": True,
            "email": company_email,
            "company": get_company_name(state["jobs_data"])
        }
    return state


# 🔥 DYNAMIC COMPANY NAME EXTRACTOR
def get_company_name(jobs_data: Dict[str, Any]) -> str:
    """Extract company name from multiple sources - NO HARDCODING"""
    sources = [
        jobs_data.get("source", {}).get("company_name"),
        jobs_data.get("source", {}).get("title"),
        jobs_data.get("contact_information", {}).get("company"),
        jobs_data.get("metadata", {}).get("company")
    ]
    
    for source in sources:
        if source and isinstance(source, str) and len(source) > 3:
            return source.strip()
    
    # Extract from URL as last resort
    url = jobs_data.get("source", {}).get("url", "")
    if "mastercard" in url.lower():
        return "Mastercard"
    if "google" in url.lower():
        return "Google"
    if "amazon" in url.lower():
        return "Amazon"
    
    return "Company"


# 🔥 LANGGRAPH WORKFLOW
workflow = StateGraph(AgentState)
workflow.add_node("parse", agent_parse_resume)
workflow.add_node("scrape", agent_scrape_jobs)
workflow.add_node("analyze", agent_analyze_groq)
workflow.add_node("email", agent_send_email)

workflow.set_entry_point("parse")
workflow.add_edge("parse", "scrape")
workflow.add_edge("scrape", "analyze")
workflow.add_conditional_edges("analyze", should_send_email, {
    "email": "email", 
    END: END
})
workflow.add_edge("email", END)

app_workflow = workflow.compile()


# 🔥 FLASK ROUTES
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        file = request.files["resume"]
        company_url = request.form["company_url"]
        
        os.makedirs("data/resume", exist_ok=True)
        resume_path = "data/resume/resume.pdf"
        file.save(resume_path)
        
        # 🔥 FIXED: Use ResumeParserV2 class PROPERLY
        parser = ResumeParserV2()
        resume_text = parser.extract_text(resume_path)  # ← FIXED: Use parser instance
        resume_info = parser.extract_basic_info(resume_text)  # ← FIXED: Use parser instance
        print(f"✅ Resume: {resume_info['name']} | {resume_info['phone']} - {len(resume_info['skills_flat'])} skills")
        
        user_id = request.form.get("user_id", "user1")
        initial_state = {
            "user_id": user_id,
            "company_url": company_url,
            "resume_data": resume_info,  # ← Pass to workflow
            "jobs_data": {},
            "analysis": {}
        }
        
        result = asyncio.run(app_workflow.ainvoke(initial_state))
        
        # 🔥 NEW: Save jobs_data for dynamic email
        try:
            os.makedirs("data/company", exist_ok=True)
            with open("data/company/last_jobs.json", "w") as f:
                json.dump(result["jobs_data"], f, indent=2)
            print(f"✅ Jobs saved for email: {len(result['jobs_data'].get('jobs', []))} jobs")
        except Exception as e:
            print(f"⚠️ Jobs save failed: {e}")
        
        # 🔥 DYNAMIC HISTORY SAVE - NO HARDCODING
        company_name = get_company_name(result["jobs_data"])
        
        # Firebase
        if FIREBASE_OK and db:
            try:
                db.collection("history").add({
                    "user_id": user_id,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                    "company_url": company_url,
                    "company": company_name[:50],
                    "jobs_count": len(result["jobs_data"].get("jobs", [])),
                    "top_match": result["analysis"].get("jobs", [{}])[0].get("match_score", 0)
                })
                print(f"✅ Firebase saved: {company_name}")
            except Exception as save_error:
                print(f"❌ Firebase save failed: {save_error}")
        
        # 🔥 LOCAL BACKUP (Always works)
        try:
            history_file = "data/history.json"
            os.makedirs("data", exist_ok=True)
            history = []
            if os.path.exists(history_file):
                with open(history_file, "r") as f:
                    history = json.load(f)
            
            history.insert(0, {
                "timestamp": datetime.now().isoformat(),
                "company_url": company_url[:50] + "...",
                "company": company_name[:50],
                "jobs_count": len(result["jobs_data"].get("jobs", [])),
                "top_match": result["analysis"].get("jobs", [{}])[0].get("match_score", 0)
            })
            history = history[:10]
            with open(history_file, "w") as f:
                json.dump(history, f)
            print(f"✅ Local saved: {company_name}")
        except Exception as local_error:
            print(f"❌ Local history failed: {local_error}")
        
        # 🔥 ENHANCED RESPONSE WITH RESUME INFO + COLD EMAIL + TOP MATCH
        top_match = result["analysis"].get("jobs", [{}])[0].get("match_score", 0)
        return jsonify({
            "success": True,
            "resume_info": resume_info,  # ← Name + Phone for email signature
            "analysis": result["analysis"],
            "jobs_count": len(result["jobs_data"].get("jobs", [])),
            "company": company_name,
            "top_match": top_match,  # ← For dynamic email
            "skills": resume_info.get('skills_detected', [])  # ← For dynamic email
        })
        
    except Exception as e:
        print(f"Analyze error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/send-email", methods=["POST"])
def send_email():
    try:
        sender = request.form["sender_email"]
        password = request.form["app_password"]
        receiver = request.form["receiver_email"]
        
        resume_path = "data/resume/resume.pdf"
        if not os.path.exists(resume_path):
            return jsonify({"success": False, "message": "No resume found"}), 400
        
        # 🔥 FIXED: Use ResumeParserV2 for send-email too
        parser = ResumeParserV2()
        resume_text = parser.extract_text(resume_path)
        resume_data = parser.extract_basic_info(resume_text)
        
        # 🔥 NEW: Load jobs_data from last analysis (data/company/last_jobs.json)
        jobs_data = {"jobs": []}
        try:
            jobs_file = "data/company/last_jobs.json"
            if os.path.exists(jobs_file):
                with open(jobs_file, "r") as f:
                    jobs_data = json.load(f)
                print(f"✅ Loaded {len(jobs_data.get('jobs', []))} jobs for email")
        except Exception as e:
            print(f"⚠️ Jobs load failed: {e}")
        
        # 🔥 UPDATED: Pass jobs_data to emailer (NEW PARAMETER!)
        success, message = send_email_with_resume(
            sender, password, receiver, resume_data, jobs_data, resume_path
        )
        
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/history", methods=["GET"])
def get_history():
    history = []
    
    # 🔥 FIREBASE FIRST
    if FIREBASE_OK and db:
        try:
            docs = db.collection("history").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
            for doc in docs:
                data = doc.to_dict()
                timestamp = (data.get("timestamp", {}).get("timestamp") if isinstance(data.get("timestamp"), dict) 
                           else data.get("timestamp", datetime.now().isoformat()))
                history.append({
                    "timestamp": timestamp,
                    "company": data.get("company", "Company")[:50] + ("..." if len(data.get("company", "")) > 50 else ""),
                    "jobs_count": data.get("jobs_count", 0),
                    "top_match": data.get("top_match", 0)
                })
        except Exception as e:
            print(f"Firebase history error: {e}")
    
    # 🔥 LOCAL FILE BACKUP
    try:
        history_file = "data/history.json"
        if os.path.exists(history_file):
            with open(history_file, "r") as f:
                local_history = json.load(f)
                history.extend(local_history[:10])
    except:
        pass
    
    # 🔥 DEDUPE + SORT
    seen = set()
    unique_history = []
    for item in history:
        key = f"{item['company']}_{item['jobs_count']}"
        if key not in seen:
            seen.add(key)
            unique_history.append(item)
    
    unique_history.sort(key=lambda x: x['timestamp'], reverse=True)
    print(f"📜 History: {len(unique_history)} unique items")
    return jsonify(unique_history[:10])


if __name__ == "__main__":
    os.makedirs("data/resume", exist_ok=True)
    os.makedirs("data/company", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    print("🚀 Job Agent Pro - GROQ 'groq/compound' + V7.3 Scraper ✅")
    print("📱 http://localhost:5000")
    app.run(debug=True, port=5000, host="0.0.0.0")
