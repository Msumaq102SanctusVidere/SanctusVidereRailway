// Simple Auth0 client
let auth0Client = null;

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, initializing application...");
    
    // Initialize Auth0
    initializeAuth0();
    
    // Set up other components
    setupReviewForm();
    setupDirectAccess();
    setupLoginButton();
    setupLogoutButton();
});

// Initialize Auth0 client
async function initializeAuth0() {
    try {
        // Config for Auth0
        const config = {
            "domain": "dev-wl2dxopsswbbvkcb.us.auth0.com",
            "clientId": "BAXPcs4GZAZodDtErS0UxTmugyxbEcZU"
        };
        
        // Create the Auth0 client
        auth0Client = await auth0.createAuth0Client({
            domain: config.domain,
            clientId: config.clientId,
            cacheLocation: "localstorage", // Required for proper logout
            authorizationParams: {
                redirect_uri: "https://app.sanctusvidere.com",
                response_type: "code",
                scope: "openid profile email"
            }
        });
        
        console.log("Auth0 client created successfully");
        
        // Handle authentication callback
        if (window.location.search.includes("code=") && 
            window.location.search.includes("state=")) {
            
            try {
                await auth0Client.handleRedirectCallback();
                window.history.replaceState({}, document.title, window.location.pathname);
                
                // Get user info & token for Streamlit app
                const user = await auth0Client.getUser();
                const token = await auth0Client.getTokenSilently();
                const userId = user.name || user.email.split('@')[0];
                
                // Redirect to Streamlit app with user=new parameter to ensure fresh instance
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&t=${Date.now()}`;
            } catch (error) {
                console.error("Error handling authentication:", error);
            }
        }
    } catch (err) {
        console.error("Error initializing Auth0:", err);
    }
}

// Setup login button
function setupLoginButton() {
    const loginButton = document.getElementById('auth0-login-button');
    if (loginButton) {
        loginButton.addEventListener('click', function(e) {
            e.preventDefault();
            loginWithAuth0();
        });
    }
}

// Setup logout button - using Auth0 sample's logout implementation
function setupLogoutButton() {
    const logoutButton = document.getElementById('auth0-logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', function(e) {
            console.log("Logout button clicked");
            e.preventDefault();
            logout();
        });
    }
}

// Login with Auth0
async function loginWithAuth0() {
    try {
        console.log("Logging in...");
        await auth0Client.loginWithRedirect({
            authorizationParams: {
                redirect_uri: "https://app.sanctusvidere.com"
            }
        });
    } catch (err) {
        console.error("Login failed:", err);
    }
}

// Logout function directly from Auth0 sample - FIXED with explicit returnTo URL
const logout = async () => {
    try {
        console.log("Logging out...");
        await auth0Client.logout({
            logoutParams: {
                returnTo: "https://sanctusvidere.com"
            }
        });
    } catch (err) {
        console.log("Log out failed", err);
    }
};

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
