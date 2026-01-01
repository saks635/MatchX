import os
import re
import json
import sys
import io
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from collections import Counter, defaultdict
import logging
from PyPDF2 import PdfReader
import hashlib


# 🔥 WINDOWS UNICODE FIX (CRITICAL)
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def safe_arrow():
    return " -> " if sys.platform.startswith('win') else " → "


# 🔥 WINDOWS-SAFE LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('data/parser.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ResumeParserV2:
    """🔥 PRODUCTION-GRADE Resume Parser - Windows Compatible"""
    
    SKILLS_DATABASE = {
        'programming': ['python', 'java', 'javascript', 'typescript', 'cpp', 'c++', 'c#', 'go', 'rust', 'swift', 'kotlin', 'scala', 'php', 'ruby'],
        'frontend': ['react', 'angular', 'vue', 'svelte', 'nextjs', 'html', 'css', 'tailwind', 'bootstrap'],
        'backend': ['node', 'express', 'django', 'flask', 'spring', 'laravel'],
        'database': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis'],
        'cloud': ['aws', 'azure', 'gcp', 'docker', 'kubernetes'],
        'devops': ['git', 'github', 'jenkins', 'terraform', 'ansible']
    }
    
    def __init__(self):
        self.cache = {}
    
    def process_resume(self, file_path: str) -> Dict[str, Any]:
        file_hash = self._get_file_hash(file_path)
        if file_hash in self.cache:
            return self.cache[file_hash]
        
        text = self.extract_text(file_path)
        info = self.extract_basic_info(text)
        
        result = {
            **info,
            "file_path": str(Path(file_path).absolute()),
            "file_size": os.path.getsize(file_path),
            "file_hash": file_hash,
            "processed_at": datetime.now().isoformat()
        }
        self.cache[file_hash] = result
        return result
    
    def extract_text(self, file_path: str) -> str:
        file_ext = Path(file_path).suffix.lower()
        if file_ext == ".pdf":
            return self._extract_pdf_advanced(file_path)
        return self._extract_text_file(file_path)
    
    def _extract_pdf_advanced(self, file_path: str) -> str:
        try:
            reader = PdfReader(file_path)
            full_text = []
            for i, page in enumerate(reader.pages[:10]):
                try:
                    text = page.extract_text()
                    if text:
                        lines = [line.strip() for line in text.split('\n') if line.strip()]
                        content_lines = [line for line in lines if len(line) > 3]
                        if content_lines:
                            full_text.append(f"[PAGE {i+1}] {' '.join(content_lines[:20])}")
                except:
                    continue
            result = ' '.join(full_text)[:5000]
            arrow = safe_arrow()
            logger.info(f"PDF: {len(reader.pages)} pages{arrow}{len(result)} chars")
            return result
        except Exception as e:
            logger.error(f"PDF failed: {e}")
            return ""
    
    def _extract_text_file(self, file_path: str) -> str:
        for enc in ['utf-8', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()[:5000]
            except:
                continue
        return ""
    
    # 🔥 FIXED: extract_basic_info AS CLASS METHOD
    def extract_basic_info(self, text: str) -> Dict[str, Any]:
        """Enhanced: Extract name, phone, skills, email from resume text"""
        
        # 🔥 PHONE NUMBER PATTERNS (Indian + International)
        phone_patterns = [
            r'(\+?91|0)?[6-9]\d{9}',  # India: 9876543210, +919876543210
            r'(\+?1)?[2-9]\d{9}',     # US: 1234567890
            r'(\d{3}[-.]?\d{3}[-.]?\d{4})',  # Formatted: 123-456-7890
        ]
        phones = []
        for pattern in phone_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            phones.extend(matches)
        phone = phones[0] if phones else "[Your Phone]"
        
        # 🔥 NAME PATTERNS (First lines, bold text, common positions)
        lines = text.split('\n')[:10]
        name = "[Your Name]"
        for line in lines:
            match = re.match(r'^[A-Z][a-z]{2,20}\s+[A-Z][a-z]{2,20}', line.strip())
            if match:
                name = match.group(0).strip()
                break
        
        # 🔥 EMAIL PATTERN
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        email = email_match.group() if email_match else "email@example.com"
        
        # 🔥 FIXED: Use self._extract_skills_enhanced() - NO EXTERNAL FUNCTION
        skills_detected = self._extract_skills_enhanced(text.lower())
        skills_by_category = self._categorize_skills(skills_detected)
        
        return {
            "name": name,
            "phone": phone,
            "email": email,
            "skills": skills_by_category,  # Dict by category
            "skills_detected": skills_detected,  # Flat list
            "skills_flat": skills_detected,  # For LangGraph compatibility
            "raw_text": text[:5000],
            "confidence": 0.95
        }
    
    def _extract_skills_enhanced(self, text_lower: str) -> List[str]:
        """Extract skills using internal database"""
        skills = []
        for category, keywords in self.SKILLS_DATABASE.items():
            for skill in keywords:
                if skill in text_lower:
                    skills.append(skill)
        return list(set(skills))[:20]
    
    def _categorize_skills(self, skills: List[str]) -> Dict[str, List[str]]:
        """Categorize skills by type"""
        categorized = defaultdict(list)
        for skill in skills:
            for category, keywords in self.SKILLS_DATABASE.items():
                if skill in keywords:
                    categorized[category].append(skill)
                    break
        return dict(categorized)
    
    def _extract_name_improved(self, lines: List[str], text_lower: str) -> str:
        # Strategy 1: First line
        if lines and re.match(r'^[A-Z][a-z]+\s+[A-Z]', lines[0]):
            return lines[0].split()[0:2]
        
        # Strategy 2: Email-based
        email_match = re.search(r'([a-zA-Z]+)[.@]', text_lower)
        if email_match:
            return email_match.group(1).title()
        
        return "Candidate"
    
    def _get_file_hash(self, file_path: str) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


# 🔥 BACKWARD COMPATIBILITY FUNCTIONS
def extract_text(file_path: str) -> str:
    return ResumeParserV2().extract_text(file_path)


def extract_basic_info(text: str) -> Dict[str, Any]:
    return ResumeParserV2().extract_basic_info(text)


def process_resume(file_path: str) -> Dict[str, Any]:
    return ResumeParserV2().process_resume(file_path)


if __name__ == "__main__":
    test_file = "data/resume/resume.pdf"
    if os.path.exists(test_file):
        result = process_resume(test_file)
        print(f"✅ Resume: {result['name']} - {len(result['skills_detected'])} skills")
    else:
        print("📄 No test resume found at data/resume/resume.pdf")
