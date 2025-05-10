// Super simple Auth0 integration - no dependencies, minimal code

document.addEventListener('DOMContentLoaded', function() {
    // Set up buttons
    setupLoginButtons();
    setupReviewForm();
    setupDirectAccess();
    
    // Check for auth0 hash on page load (for returning from auth0)
    checkAuth0Hash();
    
    // Check if user is already logged in
    updateUIBasedOnLoginState();
});

// Auth0 configuration - UPDATED WITH NEW CLIENT ID
const config = {
    domain: 'dev-wl2dxopsswbbvkcb.us.auth0.com',
    clientId: 'aaJU2JexuNeaLvFpvIEVmgfcHeVNRsCT', // NEW CLIENT ID
    redirectUri: window.location.origin,
};

// Check for Auth0 hash on page load
function checkAuth0Hash() {
    if (window.location.hash) {
        // Parse hash
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        
        // Get tokens
        const accessToken = params.get('access_token');
        const idToken = params.get('id_token');
        
        if (accessToken && idToken) {
            // Store tokens
            localStorage.setItem('accessToken', accessToken);
            localStorage.setItem('idToken', idToken);
            
            // Get user info
            getUserInfo(accessToken);
            
            // Clear hash
            window.history.replaceState(null, null, window.location.pathname);
        }
    }
}

// Get user info from Auth0
function getUserInfo(accessToken) {
    fetch(`https://${config.domain}/userinfo`, {
        headers: {
            'Authorization': `Bearer ${accessToken}`
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(user => {
        // Store user info
        localStorage.setItem('userName', user.name || user.email.split('@')[0]);
        localStorage.setItem('userEmail', user.email);
        
        // Update UI
        updateUIBasedOnLoginState();
    })
    .catch(error => {
        console.error('Error getting user info:', error);
    });
}

// Update UI based on login state
function updateUIBasedOnLoginState() {
    const accessToken = localStorage.getItem('accessToken');
    const userName = localStorage.getItem('userName');
    
    if (accessToken && userName) {
        // User is logged in, show dashboard
        document.getElementById('login-panel').style.display = 'none';
        document.getElementById('dashboard-access').style.display = 'block';
        document.getElementById('user-name').textContent = userName;
    } else {
        // User is not logged in, show login panel
        document.getElementById('login-panel').style.display = 'block';
        document.getElementById('dashboard-access').style.display = 'none';
    }
}

// Setup login buttons
function setupLoginButtons() {
    // Login button
    const loginButton = document.getElementById('auth0-login-button');
    if (loginButton) {
        loginButton.addEventListener('click', function(e) {
            e.preventDefault();
            redirectToAuth0('login');
        });
    }
    
    // Google login button
    const googleButton = document.getElementById('auth0-google-login');
    if (googleButton) {
        googleButton.addEventListener('click', function(e) {
            e.preventDefault();
            redirectToAuth0('login', 'google-oauth2');
        });
    }
    
    // Signup button
    const signupButton = document.getElementById('auth0-signup-button');
    if (signupButton) {
        signupButton.addEventListener('click', function(e) {
            e.preventDefault();
            redirectToAuth0('signup');
        });
    }
    
    // Dashboard button
    const dashboardButton = document.querySelector('.dashboard-button');
    if (dashboardButton) {
        dashboardButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            const userId = localStorage.getItem('userName');
            const token = localStorage.getItem('accessToken');
            
            if (userId && token) {
                // Redirect to Streamlit with auth parameters
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&t=${Date.now()}`;
            } else {
                alert('Please log in first.');
            }
        });
    }
    
    // Logout button
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', function() {
            // Clear local storage
            localStorage.removeItem('accessToken');
            localStorage.removeItem('idToken');
            localStorage.removeItem('userName');
            localStorage.removeItem('userEmail');
            
            // Redirect to Auth0 logout
            window.location.href = `https://${config.domain}/v2/logout?client_id=${config.clientId}&returnTo=${encodeURIComponent(window.location.origin)}`;
        });
    }
}

// Redirect to Auth0 login or signup
function redirectToAuth0(action, connection = null) {
    let url = `https://${config.domain}/authorize?` +
        `client_id=${config.clientId}&` +
        `redirect_uri=${encodeURIComponent(config.redirectUri)}&` +
        `response_type=token%20id_token&` +
        `scope=openid%20profile%20email`;
    
    // Add connection for social login
    if (connection) {
        url += `&connection=${connection}`;
    }
    
    // Add screen_hint for signup
    if (action === 'signup') {
        url += `&screen_hint=signup`;
    }
    
    // Redirect to Auth0
    window.location.href = url;
}

// Review system functionality
function setupReviewForm() {
    // Show review form buttons
    const reviewButton = document.getElementById('review-button');
    const submitReviewButton = document.getElementById('submit-review-button');
    
    if (reviewButton) {
        reviewButton.addEventListener('click', function(e) {
            e.preventDefault();
            showReviewForm();
        });
    }
    
    if (submitReviewButton) {
        submitReviewButton.addEventListener('click', function(e) {
            e.preventDefault();
            showReviewForm();
        });
    }
    
    // Cancel review button
    const cancelReview = document.getElementById('cancel-review');
    if (cancelReview) {
        cancelReview.addEventListener('click', function() {
            hideReviewForm();
        });
    }
    
    // Review submission form
    const reviewForm = document.getElementById('review-submission');
    if (reviewForm) {
        reviewForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Get form values
            const rating = document.querySelector('input[name="rating"]:checked')?.value || 5;
            const reviewText = document.getElementById('review-text').value;
            
            if (reviewText) {
                // Store review in localStorage for demo purposes
                // In production, this would be sent to your API
                saveReview(rating, reviewText);
                
                // Hide form and show confirmation
                hideReviewForm();
                alert('Thank you for your review! Your feedback helps us improve.');
            }
        });
    }
}

// Show review form
function showReviewForm() {
    document.getElementById('review-form-container').style.display = 'flex';
}

// Hide review form
function hideReviewForm() {
    document.getElementById('review-form-container').style.display = 'none';
}

// Save review to localStorage for demo
function saveReview(rating, text) {
    const reviews = JSON.parse(localStorage.getItem('reviews') || '[]');
    const userName = localStorage.getItem('userName') || 'Anonymous User';
    
    reviews.push({
        rating: rating,
        text: text,
        user: userName,
        date: new Date().toISOString()
    });
    
    localStorage.setItem('reviews', JSON.stringify(reviews));
}

// Direct dashboard access function (emergency backup access)
function setupDirectAccess() {
    const directAccessLink = document.getElementById('admin-access-direct');
    if (directAccessLink) {
        directAccessLink.addEventListener('click', function(e) {
            e.preventDefault();
            
            const accessCode = prompt('Enter direct access code:');
            if (accessCode === 'sanctus2025') {
                window.location.href = 'https://app.sanctusvidere.com';
            } else {
                alert('Invalid access code.');
            }
        });
    }
}
