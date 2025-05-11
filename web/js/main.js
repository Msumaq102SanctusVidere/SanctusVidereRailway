// Global variable for Auth0 client - will be initialized when SDK is ready
let auth0Client = null;
let auth0Initialized = false;

// VERY IMPORTANT: Window level functions for onclick access
window.login = async function() {
    if (!auth0Initialized) {
        console.log("Auth0 not initialized yet");
        alert("Authentication is still initializing. Please try again in a moment.");
        return;
    }
    
    try {
        console.log("Logging in...");
        await auth0Client.loginWithRedirect({
            authorizationParams: {
                redirect_uri: "https://app.sanctusvidere.com"
            }
        });
    } catch (err) {
        console.error("Login failed:", err);
        alert("Login failed: " + err.message);
    }
};

window.logout = async function() {
    if (!auth0Initialized) {
        console.log("Auth0 not initialized yet");
        alert("Authentication is still initializing. Please try again in a moment.");
        return;
    }
    
    try {
        console.log("Logging out...");
        await auth0Client.logout({
            logoutParams: {
                returnTo: "https://sanctusvidere.com"
            }
        });
    } catch (err) {
        console.log("Log out failed", err);
        alert("Logout failed: " + err.message);
    }
};

// Initialize Auth0 client - SEPARATED FROM DOM READY
async function initAuth0() {
    try {
        // Check if Auth0 is available
        if (typeof auth0 === 'undefined') {
            console.error("Auth0 SDK not loaded yet");
            // Try again in a second
            setTimeout(initAuth0, 1000);
            return;
        }
        
        console.log("Initializing Auth0...");
        
        // Config for Auth0
        const config = {
            "domain": "dev-wl2dxopsswbbvkcb.us.auth0.com",
            "clientId": "BAXPcs4GZAZodDtErS0UxTmugyxbEcZU"
        };
        
        // Create the Auth0 client
        auth0Client = await auth0.createAuth0Client({
            domain: config.domain,
            clientId: config.clientId
        });
        
        auth0Initialized = true;
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

// Start Auth0 initialization process immediately
setTimeout(initAuth0, 500);

// Initialize everything when DOM is loaded - KEEP REST OF CODE AS IS
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, initializing application...");
    
    // Set up other components
    setupReviewForm();
    setupDirectAccess();
});

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
