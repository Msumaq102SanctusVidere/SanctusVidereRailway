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

// Log authentication state for debugging
async function logAuthState() {
    console.log("=== Auth State Debug ===");
    
    // Check Auth0 client
    console.log("Auth0 client exists:", auth0Client !== null);
    
    // Check if authenticated
    if (auth0Client) {
        try {
            const isAuthenticated = await auth0Client.isAuthenticated();
            console.log("Is authenticated:", isAuthenticated);
            
            if (isAuthenticated) {
                const user = await auth0Client.getUser();
                console.log("User info:", user ? "Found" : "Not found");
            }
        } catch (e) {
            console.error("Error checking auth state:", e);
        }
    }
    
    // Check localStorage
    console.log("Auth0 localStorage items:");
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.includes('auth0') || key.includes('Auth0'))) {
            console.log(" - " + key);
        }
    }
    
    console.log("========================");
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', async function() {
    try {
        await waitForAuth0SDK();
        await initializeAuth0();
        
        // Check if we've just returned from logout page
        const referrer = document.referrer;
        if (referrer && referrer.includes('logged-out.html')) {
            console.log("Returned from logout page - reinitializing Auth0");
            // Clear any remaining data
            clearAuthData();
            // Reinitialize Auth0 from scratch
            await initializeAuth0();
        }
        
        await logAuthState(); // Debug auth state
        
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
            showLoginWidget();
        });
    }
}

// Function to show the login widget
function showLoginWidget() {
    if (!lock) {
        // Reinitialize Auth0 if needed
        const config = {
            "domain": "dev-wl2dxopsswbbvkcb.us.auth0.com",
            "clientId": "BAXPcs4GZAZodDtErS0UxTmugyxbEcZU"
        };
        
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
        setupLockEvents();
    }
    
    lock.show();
}

// Set up Auth0 Lock authentication events
function setupLockEvents() {
    if (!lock) return;
    
    // Remove any existing event listeners to prevent duplicates
    lock.off('authenticated');
    
    // Add authenticated event handler
    lock.on('authenticated', function(authResult) {
        console.log('Lock authenticated event fired');
        
        // Store authentication data if needed
        if (authResult && authResult.accessToken && authResult.idToken) {
            // Get user info
            lock.getUserInfo(authResult.accessToken, function(error, profile) {
                if (error) {
                    console.error('Error getting user info:', error);
                    return;
                }
                
                // Get user ID for redirection
                const userId = profile.name || profile.email.split('@')[0];
                
                // Redirect to Streamlit app
                console.log('Redirecting to Streamlit app...');
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${authResult.idToken}&t=${Date.now()}`;
            });
        }
    });
    
    // Add authentication error event handler
    lock.on('authorization_error', function(err) {
        console.error('Lock authorization error:', err);
    });
}

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
        
        // Set up Lock events
        setupLockEvents();

        // Create the Auth0 client for session management
        auth0Client = await auth0.createAuth0Client({
            domain: config.domain,
            clientId: config.clientId,
            cacheLocation: 'localstorage'
        });
        
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
        // If client doesn't exist, attempt to reinitialize
        if (!auth0Client || !lock) {
            try {
                await initializeAuth0();
                if (!auth0Client || !lock) {
                    throw new Error("Failed to initialize Auth0");
                }
            } catch (e) {
                console.error("Error reinitializing Auth0:", e);
                // Fallback: Just show the lock if it exists
                if (lock) {
                    setupLockEvents(); // Ensure event handlers are set up
                    lock.show();
                    return;
                } else {
                    // Last resort - recreate lock directly
                    const config = {
                        "domain": "dev-wl2dxopsswbbvkcb.us.auth0.com",
                        "clientId": "BAXPcs4GZAZodDtErS0UxTmugyxbEcZU"
                    };
                    
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
                    setupLockEvents(); // Set up event handlers
                    lock.show();
                    return;
                }
            }
        }
        
        // Check if user is already logged in
        try {
            const isAuthenticated = await auth0Client.isAuthenticated();
            if (isAuthenticated) {
                // If logged in, get user info and token, then redirect to Streamlit app
                const user = await auth0Client.getUser();
                const token = await auth0Client.getTokenSilently();
                const userId = user.name || user.email.split('@')[0];
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&t=${Date.now()}`;
            } else {
                // Show the Auth0 Lock widget
                setupLockEvents(); // Ensure event handlers are set up
                lock.show();
            }
        } catch (err) {
            // If there's an error checking auth state, just show the lock widget
            console.error("Error checking auth state:", err);
            if (lock) {
                setupLockEvents(); // Ensure event handlers are set up
                lock.show();
            }
        }
    } catch (err) {
        console.error("Login failed:", err);
        alert("Authentication service is unavailable. Please try again later.");
    }
}

// Logout function - GLOBAL FUNCTION using Auth0's server-side logout
function logout() {
    // Clear local storage and cookies
    clearAuthData();
    
    // Use Auth0's official logout endpoint (most reliable method)
    const returnTo = encodeURIComponent(window.location.origin + '/logged-out.html');
    window.location.href = `https://dev-wl2dxopsswbbvkcb.us.auth0.com/v2/logout?client_id=BAXPcs4GZAZodDtErS0UxTmugyxbEcZU&returnTo=${returnTo}`;
    
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
    
    // Nullify the client reference
    auth0Client = null;
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
