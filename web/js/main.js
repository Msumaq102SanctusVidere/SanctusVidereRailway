// Direct Auth0 login - implicitly handled approach

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, setting up direct Auth0 login...");
    
    // Set up buttons
    setupLoginButtons();
    setupReviewForm();
    setupDirectAccess();
    
    // Check if user is already logged in
    checkLoginStatus();
});

// Auth0 configuration - NO CLIENT SECRET
const AUTH0_CONFIG = {
    domain: 'dev-wl2dxopsswbbvkcb.us.auth0.com',
    clientId: 'BAXPcs4GZAZodDtErS8UxTmugyxbEcZU',
    redirectUri: window.location.origin // Redirect to main page
};

// Check if user is logged in (based on localStorage)
function checkLoginStatus() {
    const token = localStorage.getItem('userToken');
    const userName = localStorage.getItem('userName');
    
    if (token && userName) {
        // User is logged in, show dashboard access
        document.getElementById('login-panel').style.display = 'none';
        document.getElementById('dashboard-access').style.display = 'block';
        document.getElementById('user-name').textContent = userName;
        
        // Also check for URL hash for returning users
        parseHashFromUrl();
    } else {
        // User is not logged in, show login panel
        document.getElementById('login-panel').style.display = 'block';
        document.getElementById('dashboard-access').style.display = 'none';
        
        // Check URL hash for tokens from Auth0 redirect
        parseHashFromUrl();
    }
}

// Parse hash from URL (for Auth0 implicit flow)
function parseHashFromUrl() {
    // Check if there's a hash in the URL
    if (window.location.hash) {
        // Parse the hash
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        
        // Check for access token
        const accessToken = params.get('access_token');
        if (accessToken) {
            // Save token
            localStorage.setItem('userToken', accessToken);
            
            // Get user info
            fetch(`https://${AUTH0_CONFIG.domain}/userinfo`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            })
            .then(response => response.json())
            .then(user => {
                // Save user info
                localStorage.setItem('userName', user.name || user.email.split('@')[0]);
                localStorage.setItem('userEmail', user.email);
                
                // Reload page to update UI
                window.location.href = window.location.origin + window.location.pathname;
            })
            .catch(error => {
                console.error('Error getting user info:', error);
                alert('Failed to get user information. Please try again.');
            });
        }
        
        // Check for error
        const error = params.get('error');
        if (error) {
            const errorDescription = params.get('error_description');
            console.error('Auth0 error:', error, errorDescription);
            alert(`Login error: ${errorDescription || error}`);
        }
        
        // Clear the hash
        window.history.replaceState(null, document.title, window.location.pathname);
    }
}

// Setup login buttons
function setupLoginButtons() {
    // Login button - Use implicit flow
    const loginButton = document.getElementById('auth0-login-button');
    if (loginButton) {
        loginButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Build Auth0 authorization URL with implicit flow
            const authUrl = `https://${AUTH0_CONFIG.domain}/authorize?` +
                `client_id=${AUTH0_CONFIG.clientId}&` +
                `redirect_uri=${encodeURIComponent(window.location.origin + window.location.pathname)}&` +
                `response_type=token&` +
                `scope=openid%20profile%20email`;
            
            // Show loading state
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
            
            // Build Auth0 authorization URL with Google connection
            const authUrl = `https://${AUTH0_CONFIG.domain}/authorize?` +
                `client_id=${AUTH0_CONFIG.clientId}&` +
                `redirect_uri=${encodeURIComponent(window.location.origin + window.location.pathname)}&` +
                `response_type=token&` +
                `connection=google-oauth2&` +
                `scope=openid%20profile%20email`;
            
            // Show loading state
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
                `redirect_uri=${encodeURIComponent(window.location.origin + window.location.pathname)}&` +
                `response_type=token&` +
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
            
            const token = localStorage.getItem('userToken');
            const userName = localStorage.getItem('userName');
            
            if (token && userName) {
                // Redirect to dashboard with token
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userName}&token=${token}&auth0=true&t=${Date.now()}`;
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
            localStorage.removeItem('userToken');
            localStorage.removeItem('userName');
            localStorage.removeItem('userEmail');
            
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
