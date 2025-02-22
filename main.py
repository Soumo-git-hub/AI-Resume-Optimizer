from flask import Flask, render_template, request, jsonify
import PyPDF2
import io
import docx2txt
import re
from typing import List, Dict
import spacy
from spacy.matcher import PhraseMatcher
from collections import Counter

# Initialize Flask app
app = Flask(__name__)

# Load spaCy model (medium version for better accuracy)
try:
    nlp = spacy.load('en_core_web_md')
except OSError:
    print("Downloading spaCy model...")
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_md"])
    nlp = spacy.load('en_core_web_md')

# Expanded skills database
SKILLS_DB = {
    'programming': ['python', 'java', 'javascript', 'c++', 'ruby', 'php', 'sql', 'r', 'swift', 'kotlin', 'go', 'rust', 'scala'],
    'web_development': ['html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'ruby on rails', 'asp.net'],
    'data_science': ['machine learning', 'deep learning', 'data analysis', 'statistics', 'pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch'],
    'cloud': ['aws', 'azure', 'google cloud', 'docker', 'kubernetes', 'serverless'],
    'databases': ['mysql', 'postgresql', 'mongodb', 'oracle', 'redis', 'elasticsearch'],
    'tools': ['git', 'jenkins', 'jira', 'confluence', 'slack', 'trello', 'agile', 'scrum'],
    'soft_skills': ['leadership', 'communication', 'teamwork', 'problem solving', 'time management', 'critical thinking', 'adaptability']
}

def extract_text_from_file(uploaded_file) -> str:
    """Extract text from PDF or DOCX files"""
    try:
        file_extension = uploaded_file.filename.split('.')[-1].lower()
        
        if file_extension == 'pdf':
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        elif file_extension in ['docx', 'doc']:
            text = docx2txt.process(uploaded_file)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
            
        return text.strip()
    except Exception as e:
        print(f"Error extracting text: {str(e)}")
        return ""

def extract_contact_info(text: str) -> Dict:
    """Extract contact information from resume"""
    contact_info = {
        'email': None,
        'phone': None,
        'linkedin': None
    }
    
    patterns = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'(\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
        'linkedin': r'(?:https?://)?(?:www\.)?linkedin\.com/\S+'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            contact_info[key] = match.group()
    
    return contact_info

def analyze_skills(doc: spacy.tokens.Doc) -> Dict[str, List[str]]:
    """Analyze skills present in the resume using PhraseMatcher"""
    found_skills = {category: [] for category in SKILLS_DB}
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    skill_to_category = {}

    # Prepare patterns and map skills to categories
    for category, skills in SKILLS_DB.items():
        for skill in skills:
            skill_lower = skill.lower()
            pattern = nlp(skill_lower)
            matcher.add(skill_lower, [pattern])
            skill_to_category[skill_lower] = category

    matches = matcher(doc)
    for match_id, start, end in matches:
        skill_name = nlp.vocab.strings[match_id]
        category = skill_to_category.get(skill_name)
        if category:
            # Add original case version from the document text
            skill_text = doc[start:end].text
            if skill_text not in found_skills[category]:
                found_skills[category].append(skill_text)

    return found_skills

def extract_education(doc: spacy.tokens.Doc) -> List[str]:
    """Extract education information from the resume"""
    education = []
    edu_keywords = ['bachelor', 'master', 'phd', 'degree', 'diploma', 'certificate']
    
    for sent in doc.sents:
        if any(keyword in sent.text.lower() for keyword in edu_keywords):
            education.append(sent.text.strip())
    
    return education

def extract_experience(doc: spacy.tokens.Doc) -> List[str]:
    """Extract work experience information from the resume"""
    experience = []
    exp_keywords = ['experience', 'work', 'job', 'position', 'role']
    
    for sent in doc.sents:
        if any(keyword in sent.text.lower() for keyword in exp_keywords):
            experience.append(sent.text.strip())
    
    return experience

def analyze_resume(text: str) -> Dict:
    """Analyze resume and provide feedback"""
    if not text.strip():
        return {
            'error': 'No text could be extracted from the resume'
        }
    
    doc = nlp(text)
    
    # Basic analysis
    word_count = len(text.split())
    skills = analyze_skills(doc)
    contact = extract_contact_info(text)
    education = extract_education(doc)
    experience = extract_experience(doc)
    
    # Generate suggestions
    suggestions = []
    
    # Length check
    if word_count < 300:
        suggestions.append("Your resume is too short. Add more details about your experience and skills.")
    elif word_count > 1000:
        suggestions.append("Your resume might be too long. Consider making it more concise while keeping important details.")
    
    # Skills check
    if not any(skills.values()):
        suggestions.append("No specific skills detected. Add relevant technical and soft skills that match your target job.")
    else:
        skill_count = sum(len(s) for s in skills.values())
        if skill_count < 5:
            suggestions.append("Consider adding more specific skills relevant to your field.")
        elif skill_count > 20:
            suggestions.append("You have listed many skills. Focus on the most relevant ones for the job you're applying to.")
    
    # Contact info check
    missing_contact = [k for k, v in contact.items() if not v]
    if missing_contact:
        suggestions.append(f"Add missing contact information: {', '.join(missing_contact)}. This is crucial for employers to reach you.")
    
    # Education check
    if not education:
        suggestions.append("No education information detected. Include your educational background, especially if relevant to the job.")
    elif len(education) > 3:
        suggestions.append("You've listed multiple educational entries. Focus on the most relevant ones for the job.")
    
    # Experience check
    if not experience:
        suggestions.append("No work experience detected. If you have relevant experience, make sure to highlight it.")
    elif len(experience) < 3:
        suggestions.append("Consider adding more details about your work experience, including achievements and responsibilities.")
    
    # Keyword analysis
    job_title_keywords = ['engineer', 'developer', 'manager', 'analyst', 'designer']
    found_job_titles = [kw for kw in job_title_keywords if kw in text.lower()]
    if not found_job_titles:
        suggestions.append("Consider including a clear job title or objective statement at the beginning of your resume.")
    
    # Calculate score
    score = 0
    score += min(word_count / 500 * 20, 20)  # Length score
    score += min(sum(len(s) for s in skills.values()) * 3, 30)  # Skills score
    score += (3 - len(missing_contact)) * 5  # Contact info score
    score += min(len(education) * 5, 15)  # Education score
    score += min(len(experience) * 5, 25)  # Experience score
    score += 5 if found_job_titles else 0  # Job title score
    
    return {
        'score': round(score),
        'word_count': word_count,
        'skills_found': skills,
        'contact_info': contact,
        'education': education,
        'experience': experience,  # Changed from len(experience) to return actual entries
        'suggestions': suggestions
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_endpoint():
    try:
        if 'resume' not in request.files:
            return jsonify({'error': 'No resume file uploaded'}), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        text = extract_text_from_file(file)
        if not text:
            return jsonify({'error': 'Could not extract text from file'}), 400
            
        result = analyze_resume(text)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)