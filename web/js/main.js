// Auth0 client
let auth0Client = null;

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, initializing application...");
    
    // Check if Auth0 SDK is loaded
    if (typeof createAuth0Client !== 'function') {
        console.error("Auth0 SDK not loaded! Make sure the script tag is before main.js");
        return;
    } else {
        console.log("Auth0 SDK detected");
    }
    
    // Initialize Auth0
    initializeAuth0()
        .then(() => {
            console.log("Auth0 initialized successfully");
            // Set up other components after Auth0 is initialized
            setupReviewForm();
            setupDirectAccess();
            updateUI();
        })
        .catch(err => {
            console.error("Failed to initialize Auth0:", err);
            // Show a more user-friendly error message
            document.getElementById('login-panel').innerHTML += `
                <div style="background-color: #ffdddd; padding: 10px; border-radius: 4px; margin-top: 10px;">
                    <p>There was a problem connecting to the authentication service. Please try again later.</p>
                    <p><small>Error: ${err.message || 'Unknown error'}</small></p>
                </div>
            `;
        });
});

// Initialize Auth0 client
async function initializeAuth0() {
    try {
        // Config from auth_config.json - hardcoded for simplicity
        const config = {
            "domain": "dev-wl2dxopsswbbvkcb.us.auth0.com",
            "clientId": "BAXPcs4GZAZodDtErS0UxTmugyxbEcZU"
        };
        
        console.log("Creating Auth0 client with config:", config);
        
        // Create the Auth0 client with cookie-friendly settings
        auth0Client = await createAuth0Client({
            domain: config.domain,
            clientId: config.clientId,
            authorizationParams: {
                redirect_uri: window.location.origin,
                response_type: "code",
                scope: "openid profile email"
            },
            cacheLocation: "localstorage", // Use localStorage instead of cookies
            useRefreshTokens: true,
            useFormData: true // Important for newer Chrome versions
        });
        
        console.log("Auth0 client created successfully");
        
        // Handle the authentication callback
        if (window.location.search.includes("code=") && 
            window.location.search.includes("state=")) {
            
            console.log("Auth callback detected in URL, handling redirect...");
            
            try {
                const result = await auth0Client.handleRedirectCallback();
                console.log("Redirect handled successfully:", result);
                
                // Clear the URL
                window.history.replaceState({}, document.title, window.location.pathname);
                
                console.log("Logged in successfully!");
            } catch (callbackError) {
                console.error("Error handling redirect:", callbackError);
                throw callbackError;
            }
        }
        
    } catch (err) {
        console.error("Error initializing Auth0:", err);
        throw err;
    }
}

// Login function - UPDATED FOR V2 SDK with origin-based URI
async function login() {
    try {
        console.log("Logging in... Current origin:", window.location.origin);
        
        // Updated syntax for v2 - using window.location.origin
        await auth0Client.loginWithRedirect({
            authorizationParams: {
                redirect_uri: window.location.origin
            }
        });
        
        // Note: The page will redirect to Auth0, so code after this point won't execute
    } catch (err) {
        console.error("Login failed:", err);
        alert("Login failed: " + (err.message || "Unknown error"));
    }
}

// Logout function - UPDATED FOR V2 SDK
async function logout() {
    try {
        console.log("Logging out...");
        
        // Updated syntax for v2
        auth0Client.logout({
            logoutParams: {
                returnTo: window.location.origin
            }
        });
        
        // Note: The page will redirect to logout URL, so code after this point won't execute
    } catch (err) {
        console.error("Logout failed:", err);
    }
}

// Update UI based on authentication state
async function updateUI() {
    try {
        const isAuthenticated = await auth0Client.isAuthenticated();
        console.log("Authentication check result:", isAuthenticated);
        
        if (isAuthenticated) {
            // User is logged in
            console.log("User is authenticated");
            
            // Get user info
            const user = await auth0Client.getUser();
            console.log("User info retrieved:", user);
            
            // Update UI - show dashboard, hide login
            document.getElementById('login-panel').style.display = 'none';
            document.getElementById('dashboard-access').style.display = 'block';
            document.getElementById('user-name').textContent = user.name || user.email;
            
            // Store user info for Streamlit
            const token = await auth0Client.getTokenSilently();
            localStorage.setItem('userToken', token);
            localStorage.setItem('userName', user.name || user.email.split('@')[0]);
            localStorage.setItem('userEmail', user.email);
            console.log("User info stored in localStorage");
        } else {
            // User is not logged in
            console.log("User is not authenticated");
            
            // Update UI - hide dashboard, show login
            document.getElementById('login-panel').style.display = 'block';
            document.getElementById('dashboard-access').style.display = 'none';
            
            // Setup login buttons
            setupLoginButtons();
        }
    } catch (err) {
        console.error("Error updating UI:", err);
    }
}

// Setup login buttons
function setupLoginButtons() {
    console.log("Setting up login buttons");
    
    // Login button
    const loginButton = document.getElementById('auth0-login-button');
    if (loginButton) {
        console.log("Login button found");
        loginButton.addEventListener('click', function(e) {
            console.log("Login button clicked");
            e.preventDefault();
            login();
        });
    } else {
        console.warn("Login button not found with ID: auth0-login-button");
    }
    
    // Google login button
    const googleButton = document.getElementById('auth0-google-login');
    if (googleButton) {
        console.log("Google login button found");
        googleButton.addEventListener('click', function(e) {
            console.log("Google login button clicked");
            e.preventDefault();
            login();
        });
    } else {
        console.warn("Google login button not found with ID: auth0-google-login");
    }
    
    // Signup button
    const signupButton = document.getElementById('auth0-signup-button');
    if (signupButton) {
        console.log("Signup button found");
        signupButton.addEventListener('click', function(e) {
            console.log("Signup button clicked");
            e.preventDefault();
            login();
        });
    } else {
        console.warn("Signup button not found with ID: auth0-signup-button");
    }
    
    // Dashboard button
    const dashboardButton = document.querySelector('.dashboard-button');
    if (dashboardButton) {
        console.log("Dashboard button found");
        dashboardButton.addEventListener('click', async function(e) {
            console.log("Dashboard button clicked");
            e.preventDefault();
            
            const isAuthenticated = await auth0Client.isAuthenticated();
            
            if (isAuthenticated) {
                const token = await auth0Client.getTokenSilently();
                const user = await auth0Client.getUser();
                const userId = user.name || user.email.split('@')[0];
                
                // Redirect to Streamlit app with token and user ID
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&t=${Date.now()}`;
            } else {
                alert('You need to be logged in to access the dashboard.');
            }
        });
    } else {
        console.warn("Dashboard button not found with class: dashboard-button");
    }
    
    // Logout button
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        console.log("Logout button found");
        logoutButton.addEventListener('click', function(e) {
            console.log("Logout button clicked");
            e.preventDefault();
            logout();
        });
    } else {
        console.warn("Logout button not found with ID: logout-button");
    }
    
    console.log("Login buttons setup complete");
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

// Add debugging helper function
window.checkAuth0Status = function() {
    console.log("=== Auth0 Status Check ===");
    console.log("Auth0 client initialized:", !!auth0Client);
    console.log("Current URL:", window.location.href);
    console.log("Origin:", window.location.origin);
    
    const loginButton = document.getElementById('auth0-login-button');
    console.log("Login button exists:", !!loginButton);
    
    const googleButton = document.getElementById('auth0-google-login');
    console.log("Google login button exists:", !!googleButton);
    
    console.log("Current DOM structure of login panel:");
    const loginPanel = document.getElementById('login-panel');
    if (loginPanel) {
        console.log(loginPanel.innerHTML);
    } else {
        console.log("Login panel not found");
    }
    
    console.log("=== End Status Check ===");
    
    return "Auth0 status check complete - see console for details";
};

// Check HTML elements after a delay to ensure they're loaded
setTimeout(() => {
    console.log("Running delayed HTML element check");
    window.checkAuth0Status();
}, 3000);
