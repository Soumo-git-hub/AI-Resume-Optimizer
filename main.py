from flask import Flask, render_template, request, jsonify
import pdfplumber
import io
import docx2txt
import re
import spacy
from spacy.matcher import PhraseMatcher
from collections import Counter, defaultdict
import dateparser
from datetime import datetime, date
import language_tool_python
import itertools
import spacy.cli

app = Flask(__name__)

# Configuration
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
SKILLS_DB = {
    'technical': [
        'python', 'java', 'sql', 'aws', 'docker', 'machine learning',
        'react', 'node.js', 'mongodb', 'tableau', 'spark', 'keras',
        'tensorflow', 'pytorch', 'git', 'jenkins', 'linux', 'rest api',
        'nosql', 'big data', 'ci/cd', 'kubernetes', 'azure', 'google cloud'
    ],
    'soft': [
        'leadership', 'communication', 'teamwork', 'problem solving',
        'time management', 'critical thinking', 'adaptability',
        'creativity', 'emotional intelligence', 'negotiation', 'mentoring'
    ],
    'certifications': [
        'pmp', 'aws certified', 'cisco certified', 'microsoft certified',
        'google cloud certified', 'scrum master', 'cissp', 'ceh',
        'itil certification', 'aws solutions architect'
    ],
    'tools': [
        'jira', 'confluence', 'slack', 'trello', 'docker', 'postman',
        'visual studio code', 'intellij idea', 'tableau', 'power bi'
    ]
}
ACTION_VERBS = [
    'achieved', 'managed', 'developed', 'led', 'implemented', 'increased',
    'reduced', 'optimized', 'created', 'spearheaded', 'improved', 'designed',
    'architected', 'transformed', 'automated', 'mentored', 'negotiated',
    'published', 'presented', 'streamlined'
]

# SpaCy model loading - moved to app initialization 
nlp = None

# Initialize grammar checker - moved to lazy loading
tool = None

def initialize_nlp():
    global nlp
    if nlp is None:
        try:
            nlp = spacy.load('en_core_web_md')
        except OSError:
            try:
                spacy.cli.download('en_core_web_md')
                nlp = spacy.load('en_core_web_md')
            except Exception as e:
                raise RuntimeError(f"Failed to load NLP model: {str(e)}")
    return nlp

def initialize_grammar_tool():
    global tool
    if tool is None:
        tool = language_tool_python.LanguageTool('en-US')
    return tool

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(uploaded_file):
    """Extract text from PDF/DOCX files using pdfplumber and docx2txt"""
    try:
        content = uploaded_file.read()
        file_extension = uploaded_file.filename.split('.')[-1].lower()

        if file_extension == 'pdf':
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                return '\n'.join([page.extract_text() or '' for page in pdf.pages])
        elif file_extension in ['docx', 'doc']:
            return docx2txt.process(io.BytesIO(content))
        else:
            raise ValueError("Unsupported file format")
    except Exception as e:
        raise RuntimeError(f"Text extraction failed: {str(e)}")

def analyze_experience_gaps(dates, gap_threshold=60):
    """Analyze employment history gaps with configurable threshold"""
    if len(dates) < 2:
        return []
    
    # Convert all dates to datetime.date for consistent comparison
    sorted_dates = sorted([d.date() if hasattr(d, 'date') else d for d in dates if d is not None])
    gaps = []

    for prev_end, current_start in zip(sorted_dates[:-1], sorted_dates[1:]):
        gap_days = (current_start - prev_end).days
        if gap_days > gap_threshold:
            gaps.append({
                'start': prev_end.strftime('%b %Y'),
                'end': current_start.strftime('%b %Y'),
                'duration': f"{(gap_days//30)} months"
            })
    
    return gaps

def extract_contact_info(text):
    """Extract contact information from resume"""
    # Added missing function
    contact = {
        'email': None,
        'phone': None,
        'linkedin': None,
        'website': None
    }
    
    # Email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, text)
    if email_match:
        contact['email'] = email_match.group()
    
    # Phone pattern
    phone_pattern = r'(\+\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\d{10})'
    phone_match = re.search(phone_pattern, text)
    if phone_match:
        contact['phone'] = phone_match.group()
    
    # LinkedIn pattern
    linkedin_pattern = r'(?:linkedin\.com/in/|linkedin:)([a-zA-Z0-9_-]+)'
    linkedin_match = re.search(linkedin_pattern, text, re.IGNORECASE)
    if linkedin_match:
        contact['linkedin'] = linkedin_match.group()
    
    # Website pattern
    website_pattern = r'https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:/\S*)?'
    website_match = re.search(website_pattern, text)
    if website_match and 'linkedin' not in website_match.group().lower():
        contact['website'] = website_match.group()
    
    return contact

def analyze_structure(text):
    """Analyze resume structure and formatting"""
    # Added missing function
    structure = {
        'sections': [],
        'section_order_score': 0,
        'format_issues': [],
        'length': len(text.split())
    }
    
    # Detect common section headers
    section_patterns = {
        'summary': r'\b(?:SUMMARY|PROFILE|OBJECTIVE)\b',
        'experience': r'\b(?:EXPERIENCE|WORK|EMPLOYMENT|HISTORY)\b',
        'education': r'\b(?:EDUCATION|ACADEMIC|DEGREE|UNIVERSITY)\b',
        'skills': r'\b(?:SKILLS|EXPERTISE|COMPETENCIES)\b',
        'projects': r'\b(?:PROJECTS|PORTFOLIO)\b',
        'certifications': r'\b(?:CERTIFICATIONS|CERTIFICATES)\b',
        'references': r'\b(?:REFERENCES)\b'
    }
    
    # Find sections
    for section, pattern in section_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            structure['sections'].append(section)
    
    # Check section order - ideal order defined here
    ideal_order = ['summary', 'experience', 'skills', 'education', 'projects', 'certifications', 'references']
    
    # Calculate section order score based on comparison to ideal order
    if structure['sections']:
        # Find sections in common with ideal order
        common_sections = [s for s in structure['sections'] if s in ideal_order]
        
        if common_sections:
            # Get the indices of common sections in the ideal order
            ideal_indices = {section: i for i, section in enumerate(ideal_order)}
            
            # Extract the order of common sections in the resume
            current_order = []
            for section in ideal_order:
                if section in common_sections:
                    current_order.append(section)
            
            # Calculate order score (higher if matches ideal order)
            ideal_pairs = list(zip(current_order, current_order[1:]))
            actual_pairs = []
            
            for i in range(len(common_sections) - 1):
                if ideal_indices[common_sections[i]] < ideal_indices[common_sections[i+1]]:
                    actual_pairs.append((common_sections[i], common_sections[i+1]))
            
            if ideal_pairs:
                structure['section_order_score'] = int((len(actual_pairs) / len(ideal_pairs)) * 100)
            else:
                structure['section_order_score'] = 50  # Default score if only one section found
        else:
            structure['section_order_score'] = 0
    else:
        structure['format_issues'].append("No standard sections detected")
        structure['section_order_score'] = 0
    
    # Check for formatting issues
    if structure['length'] < 300:
        structure['format_issues'].append("Resume is too short")
    elif structure['length'] > 1500:
        structure['format_issues'].append("Resume is too lengthy")
    
    # Check for missing crucial sections
    if 'experience' not in structure['sections'] and 'projects' not in structure['sections']:
        structure['format_issues'].append("Missing experience or projects section")
    
    if 'education' not in structure['sections']:
        structure['format_issues'].append("Missing education section")
    
    if 'skills' not in structure['sections']:
        structure['format_issues'].append("Missing skills section")
    
    return structure

def analyze_experience(text):
    """Analyze work experience with NLP-based verb detection"""
    initialize_nlp()  # Initialize NLP lazily
    
    experience = {
        'jobs': [],
        'action_verbs': [],
        'durations': [],
        'achievements': [],
        'gaps': [],
        'verb_variety_score': 0
    }

    # Date parsing
    date_ranges = re.findall(
        r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4})\b.*?\b(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}|Present)\b', 
        text, 
        re.IGNORECASE
    )
    
    # Process date ranges
    for start_str, end_str in date_ranges:
        start_date = dateparser.parse(start_str)
        end_date = dateparser.parse(end_str) if end_str.lower() != 'present' else date.today()
        if start_date and end_date:
            experience['durations'].append((start_date, end_date))
    
    # Calculate gaps - convert all dates to date objects for consistent comparison
    all_dates = []
    for start, end in experience['durations']:
        all_dates.append(start.date() if hasattr(start, 'date') else start)
        all_dates.append(end.date() if hasattr(end, 'date') else end)
    
    experience['gaps'] = analyze_experience_gaps(all_dates)

    # NLP-based analysis
    doc = nlp(text)
    
    # Extract job titles
    experience['jobs'] = [ent.text for ent in doc.ents if ent.label_ == 'ORG']
    
    # Action verbs detection
    verbs = [token.lemma_.lower() for token in doc if token.pos_ == "VERB" and token.lemma_.lower() in ACTION_VERBS]
    experience['action_verbs'] = list(set(verbs))
    experience['verb_variety_score'] = min(len(verbs) * 10, 100)

    # Achievements detection
    achievement_pattern = r'\b(Increased|Reduced|Improved|Saved|Grew|Optimized|Accelerated)\b.*?(\d+%|\$\d+|\d+x)'
    experience['achievements'] = re.findall(achievement_pattern, text, re.IGNORECASE)

    return experience

def check_grammar(text):
    """Check grammar on first 1000 words for efficiency"""
    initialize_grammar_tool()  # Initialize grammar tool lazily
    
    truncated = ' '.join(text.split()[:1000])
    matches = tool.check(truncated)
    return [{
        'message': match.message,
        'context': match.context,
        'replacements': match.replacements[:3]  # Limit replacements for efficiency
    } for match in matches]

def analyze_skills(text):
    """Match skills using NLP phrase matching"""
    initialize_nlp()  # Initialize NLP lazily
    
    doc = nlp(text.lower())
    skills_found = {category: [] for category in SKILLS_DB}
    
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    for category, terms in SKILLS_DB.items():
        patterns = [nlp(term) for term in terms]
        matcher.add(category, patterns)
    
    matches = matcher(doc)
    for match_id, start, end in matches:
        category = nlp.vocab.strings[match_id]
        skill = doc[start:end].text
        if skill not in skills_found[category]:
            skills_found[category].append(skill.title())
    
    return skills_found

def generate_score(analysis):
    """Dynamic weighted scoring system"""
    weights = {
        'contact': 0.15,
        'structure': 0.20,
        'skills': 0.25,
        'experience': 0.30,
        'grammar': 0.10
    }

    scores = {
        'contact': min(len([v for v in analysis['contact'].values() if v]) * 20, 100),
        'structure': max(0, 100 - len(analysis['structure']['format_issues']) * 5),
        'skills': min(sum(len(v) for v in analysis['skills'].values()) * 4, 100),
        'experience': min(
            (len(analysis['experience']['jobs']) * 5 +
             len(analysis['experience']['achievements']) * 10 +
             analysis['experience']['verb_variety_score']),
            100
        ),
        'grammar': max(100 - len(analysis['grammar']) * 2, 0)
    }

    total_score = sum(scores[cat] * weight for cat, weight in weights.items())
    return round(min(max(total_score, 0), 100))

def generate_recommendations(analysis):
    """Generate personalized recommendations"""
    recommendations = []
    
    # Contact recommendations
    if not analysis['contact']['email'] or not analysis['contact']['phone']:
        recommendations.append("Include both email and phone number for better accessibility")
    
    # Structure recommendations
    if analysis['structure']['section_order_score'] < 80:
        recommendations.append("Improve section ordering for better readability")
    
    # Skills recommendations
    if len(analysis['skills']['technical']) < 5:
        recommendations.append("Add more technical skills relevant to your target role")
    
    # Experience recommendations
    if not analysis['experience']['achievements']:
        recommendations.append("Include quantifiable achievements with metrics")
    
    if analysis['experience']['gaps']:
        recommendations.append(f"Address {len(analysis['experience']['gaps'])} employment gaps in your resume")
    
    # Grammar recommendations
    if analysis['grammar']:
        recommendations.append(f"Fix {len(analysis['grammar'])} grammar/spelling issues")
    
    return recommendations

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['resume']
    if not file.filename or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed types: PDF, DOCX'}), 400

    try:
        text = extract_text_from_file(file)
        analysis = {
            'contact': extract_contact_info(text),
            'structure': analyze_structure(text),
            'skills': analyze_skills(text),
            'experience': analyze_experience(text),
            'grammar': check_grammar(text)
        }
        
        analysis['score'] = generate_score(analysis)
        analysis['recommendations'] = generate_recommendations(analysis)
        
        return jsonify(analysis)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Replace the deprecated @app.before_first_request decorator
# with proper initialization using app context
@app.before_request
def initialize_services_if_needed():
    # Initialize services on demand rather than at startup
    if request.endpoint == 'analyze':
        initialize_nlp()
        # Grammar tool will be initialized on first use

if __name__ == '__main__':
    app.run(debug=True)