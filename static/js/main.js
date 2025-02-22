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
			throw new Error(data.error || 'Analysis failed');
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
	document.getElementById('score').textContent = data.score;

	// Update skills
	const skillsContainer = document.getElementById('skills');
	skillsContainer.innerHTML = Object.entries(data.skills_found)
		.map(([category, skills]) => `
			<div class="skill-item">
				<strong>${formatCategory(category)}:</strong>
				<p>${skills.length ? skills.join(', ') : 'None found'}</p>
			</div>
		`)
		.join('');

	// Update contact info
	const contactContainer = document.getElementById('contact');
	contactContainer.innerHTML = Object.entries(data.contact_info)
		.map(([type, value]) => `
			<div class="skill-item">
				<strong>${formatCategory(type)}:</strong>
				<p>${value || 'Not found'}</p>
			</div>
		`)
		.join('');

	// Update suggestions
	const suggestionsContainer = document.getElementById('suggestions');
	suggestionsContainer.innerHTML = data.suggestions
		.map(suggestion => `
			<li class="suggestion-item">
				${suggestion}
			</li>
		`)
		.join('');
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