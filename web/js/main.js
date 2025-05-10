// Simple Auth0 Lock integration for your HTML service

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, initializing Auth0 Lock...");
    
    // Initialize Auth0 Lock
    initAuth0Lock();
    
    // Setup other components
    setupReviewForm();
    setupDirectAccess();
});

// Auth0 configuration
const AUTH0_CONFIG = {
    domain: 'dev-wl2dxopsswbbvkcb.us.auth0.com',
    clientId: 'BAXPcs4GZAZodDtErS8UxTmugyxbEcZU',
    callbackUrl: 'https://sanctusvidere.com/callback.html',
    audience: `https://${AUTH0_CONFIG.domain}/userinfo`,
    responseType: 'token id_token',
    scope: 'openid profile email'
};

// Initialize Auth0 Lock widget
function initAuth0Lock() {
    // Check if user is already logged in
    checkSession();
    
    // Setup login buttons
    setupLoginButtons();
}

// Check if user is already logged in
function checkSession() {
    // Check for tokens in localStorage
    const accessToken = localStorage.getItem('accessToken');
    const idToken = localStorage.getItem('idToken');
    const profile = localStorage.getItem('userProfile');
    
    if (accessToken && idToken && profile) {
        // User is already logged in, show dashboard
        showDashboard(JSON.parse(profile));
    } else {
        // Parse hash on page load
        parseHash();
    }
}

// Parse hash from URL after Auth0 redirect
function parseHash() {
    // Get hash from URL
    const hash = window.location.hash;
    
    if (hash && (hash.indexOf('access_token') > -1)) {
        // Parse hash
        const accessToken = getValueFromHash('access_token', hash);
        const idToken = getValueFromHash('id_token', hash);
        
        if (accessToken && idToken) {
            // Store tokens
            localStorage.setItem('accessToken', accessToken);
            localStorage.setItem('idToken', idToken);
            
            // Get user profile
            getUserProfile(accessToken);
            
            // Clear hash
            history.pushState('', document.title, window.location.pathname);
        }
    }
}

// Get value from hash
function getValueFromHash(key, hash) {
    const matches = hash.match(new RegExp(key + '=([^&]*)'));
    return matches ? matches[1] : null;
}

// Get user profile
function getUserProfile(accessToken) {
    // Make request to Auth0 userinfo endpoint
    fetch(`https://${AUTH0_CONFIG.domain}/userinfo`, {
        headers: {
            'Authorization': `Bearer ${accessToken}`
        }
    })
    .then(response => response.json())
    .then(profile => {
        // Store profile
        localStorage.setItem('userProfile', JSON.stringify(profile));
        
        // Show dashboard
        showDashboard(profile);
    })
    .catch(error => {
        console.error('Error getting user profile:', error);
    });
}

// Show dashboard
function showDashboard(profile) {
    // Update UI - hide login panel, show dashboard
    document.getElementById('login-panel').style.display = 'none';
    document.getElementById('dashboard-access').style.display = 'block';
    
    // Update user name
    document.getElementById('user-name').textContent = profile.name || profile.email.split('@')[0];
}

// Setup Auth0 login buttons
function setupLoginButtons() {
    // Main login button
    const loginButton = document.getElementById('auth0-login-button');
    if (loginButton) {
        loginButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Build Auth0 authorization URL for regular login
            const authUrl = `https://${AUTH0_CONFIG.domain}/authorize?` +
                `client_id=${AUTH0_CONFIG.clientId}&` +
                `redirect_uri=${encodeURIComponent(window.location.origin)}&` +
                `response_type=token%20id_token&` +
                `scope=openid%20profile%20email`;
            
            // Show loading indicator
            this.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Connecting...';
            this.disabled = true;
            
            // Redirect to Auth0
            window.location.href = authUrl;
        });
    }
    
    // Google login button
    const googleButton = document.getElementById('auth0-google-login');
    if (googleButton) {
        googleButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Build Auth0 authorization URL for Google login
            const authUrl = `https://${AUTH0_CONFIG.domain}/authorize?` +
                `client_id=${AUTH0_CONFIG.clientId}&` +
                `redirect_uri=${encodeURIComponent(window.location.origin)}&` +
                `response_type=token%20id_token&` +
                `connection=google-oauth2&` +
                `scope=openid%20profile%20email`;
            
            // Show loading indicator
            this.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Connecting...';
            this.disabled = true;
            
            // Redirect to Auth0
            window.location.href = authUrl;
        });
    }
    
    // Signup button
    const signupButton = document.getElementById('auth0-signup-button');
    if (signupButton) {
        signupButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Build Auth0 authorization URL with signup hint
            const authUrl = `https://${AUTH0_CONFIG.domain}/authorize?` +
                `client_id=${AUTH0_CONFIG.clientId}&` +
                `redirect_uri=${encodeURIComponent(window.location.origin)}&` +
                `response_type=token%20id_token&` +
                `screen_hint=signup&` +
                `scope=openid%20profile%20email`;
            
            // Redirect to Auth0
            window.location.href = authUrl;
        });
    }
    
    // Dashboard button
    const dashboardButton = document.querySelector('.dashboard-button');
    if (dashboardButton) {
        dashboardButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            const accessToken = localStorage.getItem('accessToken');
            const profile = localStorage.getItem('userProfile');
            
            if (accessToken && profile) {
                // Parse profile
                const userData = JSON.parse(profile);
                const userId = userData.sub || userData.email.split('@')[0];
                
                // Redirect to dashboard with token
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${accessToken}&auth0=true&t=${Date.now()}`;
            } else {
                alert('You need to be logged in to access the dashboard.');
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
            localStorage.removeItem('userProfile');
            
            // Redirect to logout URL
            const logoutUrl = `https://${AUTH0_CONFIG.domain}/v2/logout?` +
                `client_id=${AUTH0_CONFIG.clientId}&` +
                `returnTo=${encodeURIComponent(window.location.origin)}`;
            
            window.location.href = logoutUrl;
        });
    }
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
    const userProfile = JSON.parse(localStorage.getItem('userProfile') || '{}');
    const userName = userProfile.name || userProfile.email?.split('@')[0] || 'Anonymous User';
    
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
