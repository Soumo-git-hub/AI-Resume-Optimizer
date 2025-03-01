// File input handling
document.getElementById('resumeFile').addEventListener('change', function(e) {
    const fileName = e.target.files[0]?.name || 'No file chosen';
    document.getElementById('fileName').textContent = fileName;
});

async function analyzeResume() {
    const fileInput = document.getElementById('resumeFile');
    const errorMessage = document.getElementById('error-message');
    const results = document.getElementById('results');

    // Reset UI
    errorMessage.style.display = 'none';
    results.style.display = 'none';

    // Validate input
    if (!fileInput.files[0]) {
        showError('Please select a resume file');
        return;
    }

    // Check file extension
    const fileName = fileInput.files[0].name;
    const fileExt = fileName.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'doc'].includes(fileExt)) {
        showError('Please upload a PDF or Word document (.pdf, .docx, .doc)');
        return;
    }

    // Prepare form data
    const formData = new FormData();
    formData.append('resume', fileInput.files[0]);

    try {
        // Show loading state
        document.getElementById('analyzeBtn').disabled = true;
        document.getElementById('analyzeBtn').textContent = 'Analyzing...';

        // Send request
        const response = await fetch('/analyze', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data?.error || 'Analysis failed');
        }

        displayResults(data);
    } catch (error) {
        showError(error.message || 'An error occurred during analysis');
    } finally {
        // Reset button state
        document.getElementById('analyzeBtn').disabled = false;
        document.getElementById('analyzeBtn').textContent = 'Analyze Resume';
    }
}

function displayResults(data) {
    // Show results section
    document.getElementById('results').style.display = 'block';

    // Update score
    document.getElementById('score').textContent = data.score || 0;

    // Display contact information
    const contactContainer = document.getElementById('contact');
    contactContainer.innerHTML = '';
    
    if (data.contact) {
        Object.entries(data.contact).forEach(([key, value]) => {
            if (value) {
                const div = document.createElement('div');
                div.className = 'item-card';
                div.innerHTML = `
                    <strong>${formatCategory(key)}</strong>
                    <p>${value}</p>
                `;
                contactContainer.appendChild(div);
            }
        });
    }
    
    if (contactContainer.children.length === 0) {
        contactContainer.innerHTML = '<p>No contact information detected</p>';
    }

    // Display skills
    const skillsContainer = document.getElementById('skills');
    skillsContainer.innerHTML = '';
    
    if (data.skills) {
        Object.entries(data.skills).forEach(([category, skills]) => {
            if (skills && skills.length > 0) {
                const div = document.createElement('div');
                div.className = 'item-card';
                div.innerHTML = `
                    <strong>${formatCategory(category)}</strong>
                    <p>${skills.length ? skills.join(', ') : 'None found'}</p>
                `;
                skillsContainer.appendChild(div);
            }
        });
    }

    // Display experience analysis
    const experienceContainer = document.getElementById('experience');
    experienceContainer.innerHTML = '';
    
    if (data.experience) {
        // Display action verbs
        if (data.experience.action_verbs && data.experience.action_verbs.length > 0) {
            const verbsDiv = document.createElement('div');
            verbsDiv.className = 'item-card';
            verbsDiv.innerHTML = `
                <strong>Action Verbs</strong>
                <p>${data.experience.action_verbs.join(', ')}</p>
            `;
            experienceContainer.appendChild(verbsDiv);
        }
        
        // Display achievements
        if (data.experience.achievements && data.experience.achievements.length > 0) {
            const achievementsDiv = document.createElement('div');
            achievementsDiv.className = 'item-card';
            achievementsDiv.innerHTML = `
                <strong>Achievements</strong>
                <ul>${data.experience.achievements.map(a => `<li>${a}</li>`).join('')}</ul>
            `;
            experienceContainer.appendChild(achievementsDiv);
        }
        
        // Display gaps
        if (data.experience.gaps && data.experience.gaps.length > 0) {
            const gapsDiv = document.createElement('div');
            gapsDiv.className = 'item-card';
            gapsDiv.innerHTML = `
                <strong>Employment Gaps</strong>
                <ul>${data.experience.gaps.map(g => `<li>${g.start} to ${g.end} (${g.duration})</li>`).join('')}</ul>
            `;
            experienceContainer.appendChild(gapsDiv);
        }
    }

    // Display structure analysis
    const structureContainer = document.getElementById('structure');
    structureContainer.innerHTML = '';
    
    if (data.structure) {
        // Display section order score
        const scoreDiv = document.createElement('div');
        scoreDiv.className = 'item-card';
        scoreDiv.innerHTML = `
            <strong>Section Order Score</strong>
            <p>${data.structure.section_order_score}/100</p>
        `;
        structureContainer.appendChild(scoreDiv);
        
        // Display detected sections
        if (data.structure.sections && data.structure.sections.length > 0) {
            const sectionsDiv = document.createElement('div');
            sectionsDiv.className = 'item-card';
            sectionsDiv.innerHTML = `
                <strong>Detected Sections</strong>
                <p>${data.structure.sections.map(s => formatCategory(s)).join(', ')}</p>
            `;
            structureContainer.appendChild(sectionsDiv);
        }
        
        // Display format issues
        if (data.structure.format_issues && data.structure.format_issues.length > 0) {
            const issuesDiv = document.createElement('div');
            issuesDiv.className = 'item-card';
            issuesDiv.innerHTML = `
                <strong>Format Issues</strong>
                <ul>${data.structure.format_issues.map(issue => `<li>${issue}</li>`).join('')}</ul>
            `;
            structureContainer.appendChild(issuesDiv);
        }
    }
    
    // Display grammar issues only if there are many (7+) issues
    if (data.grammar && data.grammar.length >= 7) {
        const grammarContainer = document.createElement('div');
        grammarContainer.className = 'grammar-section';
        grammarContainer.innerHTML = `
            <h3>Grammar Issues</h3>
            <div class="item-card">
                <strong>Found ${data.grammar.length} significant issues</strong>
                <ul>${data.grammar.slice(0, 5).map(issue => 
                    `<li>${issue.message} <br><em>Context: "${issue.context}"</em></li>`
                ).join('')}${data.grammar.length > 5 ? '<li>...and more</li>' : ''}</ul>
            </div>
        `;
        document.getElementById('results').appendChild(grammarContainer);
    }
    
    // Update recommendations
    const recommendationsContainer = document.getElementById('recommendations');
    if (data.recommendations && data.recommendations.length) {
        // Process recommendations to ensure dynamic counts are displayed correctly
        const processedRecommendations = data.recommendations.map(recommendation => {
            // Skip employment gaps recommendation if already displayed in experience section
            if (recommendation.includes("employment gaps")) {
                // Don't show in recommendations if already displayed in experience section
                if (data.experience?.gaps && data.experience.gaps.length > 0) {
                    return null;
                }
                return recommendation;
            }
            
            // Skip grammar recommendations entirely - we don't consider them major issues
            if (recommendation.includes("grammar/spelling issues")) {
                return null;
            }
            
            return recommendation;
        }).filter(Boolean); // Remove null items
        
        recommendationsContainer.innerHTML = processedRecommendations
            .map(r => `<li class="recommendation-item">${r}</li>`)
            .join('');
            
        if (processedRecommendations.length === 0) {
            recommendationsContainer.innerHTML = '<li class="recommendation-item">Your resume looks good! Only minor improvements needed.</li>';
        }
    } else {
        recommendationsContainer.innerHTML = '<li class="recommendation-item">No significant issues found.</li>';
    }
}

function showError(message) {
    const errorElement = document.getElementById('error-message');
    errorElement.textContent = message;
    errorElement.style.display = 'block';
}

function formatCategory(category) {
    return category
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}