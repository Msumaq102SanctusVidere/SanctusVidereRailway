// Auth0 Lock widget
let lock = null;

// Auth0 configuration
const AUTH0_CONFIG = {
    domain: "dev-wl2dxopsswbbvkcb.us.auth0.com",
    clientId: "BAXPcs4GZAZodDtErS0UxTmugyxbEcZU",
    mainUrl: "https://sanctusvidere.com",
    appUrl: "https://app.sanctusvidere.com"
};

// Wait for the Auth0 SDK to load
async function waitForAuth0SDK() {
    const maxAttempts = 50; // Wait up to 5 seconds (50 * 100ms)
    let attempts = 0;
    while (typeof Auth0Lock === 'undefined' && attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 100));
        attempts++;
    }
    if (typeof Auth0Lock === 'undefined') {
        throw new Error("Auth0 Lock SDK failed to load within 5 seconds");
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', async function() {
    try {
        await waitForAuth0SDK();
        
        // Initialize Lock
        initializeLock();
        
        // Check if we're on the logged-out page and need to show login
        if (window.location.pathname.includes('logged-out.html')) {
            setupLoginButton();
        }
    } catch (err) {
        console.error(err.message);
    }
    
    // Set up other components
    setupReviewForm();
    setupDirectAccess();
});

// Setup login button on logged-out page
function setupLoginButton() {
    const loginButton = document.getElementById('login-again-button');
    if (loginButton) {
        loginButton.addEventListener('click', function() {
            login();
        });
    }
}

// Initialize Auth0 Lock - Optimized for Streamlit's fresh workspace parameter
function initializeLock() {
    // Initialize Auth0 Lock widget with minimal configuration
    lock = new Auth0Lock(AUTH0_CONFIG.clientId, AUTH0_CONFIG.domain, {
        auth: {
            redirectUrl: AUTH0_CONFIG.mainUrl,
            responseType: 'token id_token',
            params: {
                scope: 'openid profile email'
            }
        },
        autoclose: true,
        allowSignUp: true,
        languageDictionary: {
            title: 'Sanctus Videre Login'
        },
        avatar: null
    });
    
    // Set up the authenticated event handler
    lock.on('authenticated', function(authResult) {
        // Get the tokens from the authResult
        const idToken = authResult.idToken;
        const accessToken = authResult.accessToken;
        
        // Create a redirect URL with specifically "user=new" parameter
        // This is EXACTLY what your Streamlit app is looking for!
        const redirectUrl = `${AUTH0_CONFIG.appUrl}?user=new&token=${encodeURIComponent(idToken)}&t=${Date.now()}`;
        
        console.log("Redirecting to fresh Streamlit instance:", redirectUrl);
        window.location.replace(redirectUrl);
    });
    
    console.log("Auth0 Lock initialized with proper fresh workspace parameter");
}

// Login with Auth0 Lock only
function login() {
    try {
        if (!lock) {
            // Initialize lock if not already done
            initializeLock();
        }
        
        // Simply show the lock widget
        lock.show();
    } catch (err) {
        console.error("Login failed:", err);
        alert("Authentication service unavailable. Please try again later.");
    }
}

// Logout function - IMPROVED VERSION
function logout() {
    // Clear local storage and cookies
    clearAuthData();
    
    // Use Auth0's official logout endpoint (most reliable method)
    const returnTo = encodeURIComponent(window.location.origin + '/logged-out.html');
    window.location.href = `https://${AUTH0_CONFIG.domain}/v2/logout?client_id=${AUTH0_CONFIG.clientId}&returnTo=${returnTo}`;
    
    return false;
}

// Helper function to thoroughly clear all Auth0-related data
function clearAuthData() {
    // Clear Auth0 specific items
    localStorage.removeItem('auth0:cache');
    localStorage.removeItem('auth0.is.authenticated');
    
    // Clear any token or user info
    localStorage.removeItem('access_token');
    localStorage.removeItem('id_token');
    localStorage.removeItem('expires_at');
    
    // Find and clear any Auth0-related items
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.includes('auth0') || key.includes('Auth0'))) {
            localStorage.removeItem(key);
        }
    }
    
    // Clear session storage too
    for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        if (key && (key.includes('auth0') || key.includes('Auth0'))) {
            sessionStorage.removeItem(key);
        }
    }
    
    // Clear Auth0 cookies if possible
    document.cookie.split(';').forEach(function(c) {
        document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/');
    });
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

// Direct dashboard access function
function setupDirectAccess() {
    const directAccessLink = document.getElementById('admin-access-direct');
    if (directAccessLink) {
        directAccessLink.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const accessCode = prompt('Enter direct access code:');
            if (accessCode === 'sanctus2025') {
                login();
            } else {
                alert('Invalid access code.');
            }
        });
    }
}
