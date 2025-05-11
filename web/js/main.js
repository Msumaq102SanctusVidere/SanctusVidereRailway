// The Auth0 client, initialized in initializeAuth0()
let auth0Client = null;
let lock = null;

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
        await initializeAuth0();
    } catch (err) {
        console.error(err.message);
    }
    
    // Set up other components
    setupReviewForm();
    setupDirectAccess();
});

// Initialize Auth0 client
async function initializeAuth0() {
    try {
        // Config for Auth0
        const config = {
            "domain": "dev-wl2dxopsswbbvkcb.us.auth0.com",
            "clientId": "BAXPcs4GZAZodDtErS0UxTmugyxbEcZU"
        };
        
        // Initialize Auth0 Lock widget
        lock = new Auth0Lock(config.clientId, config.domain, {
            auth: {
                redirectUrl: "https://sanctusvidere.com",
                responseType: 'code',
                params: {
                    scope: 'openid profile email'
                }
            },
            autoclose: true,
            allowSignUp: true
        });

        // Create the Auth0 client for session management
        auth0Client = await auth0.createAuth0Client({
            domain: config.domain,
            clientId: config.clientId,
            cacheLocation: 'localstorage'
        });
        
        // Show widget after logout
        if (window.location.search.includes("logout=true")) {
            lock.show();
            return; // Stop further processing to avoid Streamlit redirect
        }
        
        // Handle authentication callback only after login
        if (window.location.search.includes("code=") && 
            window.location.search.includes("state=")) {
            
            await auth0Client.handleRedirectCallback();
            window.history.replaceState({}, document.title, window.location.pathname);
            
            // Get user info & token for Streamlit app
            const user = await auth0Client.getUser();
            const token = await auth0Client.getTokenSilently();
            const userId = user.name || user.email.split('@')[0];
            
            // Redirect to Streamlit app with user=new parameter to ensure fresh instance
            window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&t=${Date.now()}`;
        }
    } catch (err) {
        console.error("Error initializing Auth0:", err);
        auth0Client = null;
    }
}

// Login with Auth0 - GLOBAL FUNCTION as in Auth0 sample
async function login() {
    try {
        if (!auth0Client || !lock) {
            throw new Error("Authentication service not available");
        }
        // Check if user is already logged in
        const isAuthenticated = await auth0Client.isAuthenticated();
        if (isAuthenticated) {
            // If logged in, get user info and token, then redirect to Streamlit app
            const user = await auth0Client.getUser();
            const token = await auth0Client.getTokenSilently();
            const userId = user.name || user.email.split('@')[0];
            window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&t=${Date.now()}`;
        } else {
            // Show the Auth0 Lock widget
            lock.show();
        }
    } catch (err) {
        console.error("Login failed:", err);
    }
}

// Logout function - GLOBAL FUNCTION as in Auth0 sample
async function logout() {
    try {
        if (!auth0Client || !lock) {
            throw new Error("Authentication service not available");
        }
        // Clear local storage to ensure clean state
        localStorage.removeItem('auth0:cache');
        // Log out from Auth0 with federated logout to clear server-side session
        await auth0Client.logout({
            logoutParams: {
                returnTo: "https://sanctusvidere.com?logout=true",
                federated: true
            }
        });
        // Ensure server-side session is cleared
        window.location.href = `https://dev-wl2dxopsswbbvkcb.us.auth0.com/v2/logout?client_id=BAXPcs4GZAZodDtErS0UxTmugyxbEcZU&returnTo=https://sanctusvidere.com?logout=true&federated`;
    } catch (err) {
        console.error("Log out failed:", err);
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
        directAccessLink.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const accessCode = prompt('Enter direct access code:');
            if (accessCode === 'sanctus2025') {
                try {
                    if (!auth0Client) {
                        throw new Error("Authentication service not available");
                    }
                    const isAuthenticated = await auth0Client.isAuthenticated();
                    if (isAuthenticated) {
                        const user = await auth0Client.getUser();
                        const token = await auth0Client.getTokenSilently();
                        const userId = user.name || user.email.split('@')[0];
                        window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&t=${Date.now()}`;
                    } else {
                        alert('You must be logged in to access the dashboard.');
                        lock.show();
                    }
                } catch (err) {
                    console.error("Direct access failed:", err);
                    alert('Failed to access dashboard. Please try logging in.');
                }
            } else {
                alert('Invalid access code.');
            }
        });
    }
}
