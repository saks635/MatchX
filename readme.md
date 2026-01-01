# 🤖 Job Agent Pro

An AI-powered **multi-agent job automation system** that parses resumes, scrapes job listings, analyzes job matches using Groq LLM, and automatically generates & sends cold emails with resume attachments.

---

## 🧠 Agent-Based Architecture

### 🧩 Agent 1 – Resume Parser
- Extracts resume text from **PDF or Image**
- Tools:
  - **MyPDF / PyPDF2** → PDF parsing
  - **EasyOCR** → Image OCR
- Outputs:
  - Name, phone, email
  - Skills (flattened)
  - Raw resume text

---

### 🌐 Agent 2 – Job Scraper
- Scrapes company career pages
- Tools:
  - **Crawl4AI**
  - **BeautifulSoup (bs4)**
- Extracts:
  - Job title
  - Location
  - Skills
  - Apply URL

---

### 🧠 Agent 3 – Groq AI Analysis
- Uses **Groq LLM (`groq/compound`)**
- Compares resume skills with job requirements
- Generates:
  - Match score (%)
  - Skill gap analysis
  - Job priority
  - Improvement suggestions

---

### 📧 Agent 4 – Cold Email Generator & Sender
- Generates personalized cold emails
- Uses:
  - Resume details
  - Best matched jobs
- Sends email automatically using:
  - **SMTP (Gmail App Password)**
- Resume attached as PDF

---

## 🔗 Role of LangGraph

**LangGraph** is used to orchestrate and control the multi-agent workflow.

It:
- Defines **agent execution order**
- Passes structured state between agents
- Supports **conditional routing**
  - Example: send cold email only if job match is low
- Improves scalability and modularity

LangGraph enables clean separation of agents while maintaining a single intelligent pipeline.

---

## 🗄️ Firebase History Storage

The system stores **job analysis history** for tracking and insights.

### 📦 Stored Data Types
Each history entry contains:
- `user_id`
- `timestamp`
- `company_name`
- `company_url`
- `jobs_count`
- `top_match_score`

### 💾 Storage Modes
- **Primary**: Firebase Firestore
- **Fallback**: Local JSON file (`data/history.json`)

### 🔍 Use Cases
- Track previously analyzed companies
- View recent job matches
- Avoid duplicate applications
- Resume job search from past history

---

## ⚙️ Tech Stack

- **Python**
- **Flask**
- **LangGraph**
- **Groq LLM**
- **EasyOCR**
- **Crawl4AI + BeautifulSoup**
- **SMTP Email Automation**
- **Firebase Firestore**
