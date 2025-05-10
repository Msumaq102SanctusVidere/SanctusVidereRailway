// main.js - Clean implementation with only Auth0 integration

// Auth0 configuration
const AUTH0_CONFIG = {
    domain: 'dev-wl2dxopsswbbvkcb.us.auth0.com',
    clientId: 'BAXPcs4GZAZodDtErS8UxTmugyxbEcZU',
    client_secret: 'v7jTmzE6fnPxuFyguFLjIBIMDiwDmEyCV-xXkIyIOuDTb5SHltLfU9h55CjOgauc',
    redirectUri: 'https://sanctusvidere.com/callback.html',
    responseType: 'code',
    scope: 'openid profile email',
    cacheLocation: 'localstorage'
};

// Global Auth0 client instance
let auth0Client = null;

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, initializing application...");
    
    // Check if Auth0 SDK is loaded
    if (typeof auth0 === 'undefined') {
        console.error("AUTH0 SDK NOT LOADED! Check script tag.");
        alert("Auth0 SDK failed to load. Please check your internet connection and try again.");
        return;
    }
    
    // Initialize Auth0 first
    initAuth0().then(() => {
        // Set up the other components after Auth0 is initialized
        setupReviewForm();
        setupDirectAccess();
        setupAuth0Buttons();
    }).catch(error => {
        console.error("Failed to initialize Auth0:", error);
    });
});

// Initialize Auth0
async function initAuth0() {
    try {
        console.log("Initializing Auth0 client...");
        
        // Create Auth0 client
        auth0Client = await auth0.createAuth0Client({
            domain: AUTH0_CONFIG.domain,
            client_id: AUTH0_CONFIG.clientId,
            client_secret: AUTH0_CONFIG.client_secret,
            redirect_uri: AUTH0_CONFIG.redirectUri,
            response_type: AUTH0_CONFIG.responseType,
            scope: AUTH0_CONFIG.scope,
            cacheLocation: AUTH0_CONFIG.cacheLocation
        });
        
        // Check for authentication callback
        if (window.location.search.includes('code=') || 
            window.location.search.includes('error=') ||
            window.location.hash.includes('access_token=')) {
            
            console.log("Auth0 callback detected, handling redirect");
            
            try {
                // Handle the redirect
                await auth0Client.handleRedirectCallback();
                console.log("Redirect handled successfully");
                
                // Clear the URL
                window.history.replaceState({}, document.title, '/');
            } catch (callbackError) {
                console.error("Error handling callback:", callbackError);
            }
        }
        
        // Check if authenticated
        const isAuthenticated = await auth0Client.isAuthenticated();
        console.log("isAuthenticated:", isAuthenticated);
        
        if (isAuthenticated) {
            console.log("User is authenticated with Auth0");
            
            // Get user info
            const user = await auth0Client.getUser();
            
            // Store user info in localStorage for easy access
            localStorage.setItem('userToken', await auth0Client.getTokenSilently());
            localStorage.setItem('userName', user.name || user.email.split('@')[0]);
            localStorage.setItem('userEmail', user.email);
            
            // Update UI to show dashboard access
            document.getElementById('login-panel').style.display = 'none';
            document.getElementById('dashboard-access').style.display = 'block';
            document.getElementById('user-name').textContent = user.name || user.email.split('@')[0];
        } else {
            console.log("User is not authenticated with Auth0");
            
            // Show login panel
            document.getElementById('login-panel').style.display = 'block';
            document.getElementById('dashboard-access').style.display = 'none';
        }
        
        return auth0Client;
        
    } catch (error) {
        console.error('Error initializing Auth0:', error);
        throw error;
    }
}

// Setup Auth0 login buttons
function setupAuth0Buttons() {
    console.log("Setting up Auth0 buttons...");
    
    // Main login button
    const loginButton = document.getElementById('auth0-login-button');
    if (loginButton) {
        loginButton.addEventListener('click', async function(e) {
            e.preventDefault();
            console.log("Auth0 login button clicked");
            
            try {
                // Show loading indicator
                this.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Connecting...';
                this.disabled = true;
                
                await auth0Client.loginWithRedirect({
                    redirect_uri: AUTH0_CONFIG.redirectUri,
                    response_type: AUTH0_CONFIG.responseType
                });
                // Note: Page will redirect, so code after this won't execute
            } catch (error) {
                console.error("Error during Auth0 login:", error);
                alert("Login error: " + error.message);
                // Reset button
                this.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
                this.disabled = false;
            }
        });
    }
    
    // Google login button
    const googleButton = document.getElementById('auth0-google-login');
    if (googleButton) {
        googleButton.addEventListener('click', async function(e) {
            e.preventDefault();
            console.log("Google login button clicked");
            
            try {
                // Show loading indicator
                this.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Connecting...';
                this.disabled = true;
                
                await auth0Client.loginWithRedirect({
                    connection: 'google-oauth2',
                    redirect_uri: AUTH0_CONFIG.redirectUri,
                    response_type: AUTH0_CONFIG.responseType
                });
                // Note: Page will redirect, so code after this won't execute
            } catch (error) {
                console.error("Error during Google login:", error);
                alert("Google login error: " + error.message);
                // Reset button
                this.innerHTML = '<i class="fab fa-google"></i> Sign in with Google';
                this.disabled = false;
            }
        });
    }
    
    // Signup button
    const signupButton = document.getElementById('auth0-signup-button');
    if (signupButton) {
        signupButton.addEventListener('click', async function(e) {
            e.preventDefault();
            console.log("Signup button clicked");
            
            try {
                await auth0Client.loginWithRedirect({
                    screen_hint: 'signup',
                    redirect_uri: AUTH0_CONFIG.redirectUri,
                    response_type: AUTH0_CONFIG.responseType
                });
                // Note: Page will redirect, so code after this won't execute
            } catch (error) {
                console.error("Error during Auth0 signup:", error);
                alert("Signup error: " + error.message);
            }
        });
    }
    
    // Dashboard button
    const dashboardButton = document.querySelector('.dashboard-button');
    if (dashboardButton) {
        dashboardButton.addEventListener('click', async function(e) {
            e.preventDefault();
            
            try {
                const isAuthenticated = await auth0Client.isAuthenticated();
                
                if (isAuthenticated) {
                    console.log("Using Auth0 token for dashboard access");
                    
                    // Get token and user info
                    const token = await auth0Client.getTokenSilently();
                    const user = await auth0Client.getUser();
                    const userId = user.sub || user.email.split('@')[0];
                    
                    // Redirect to dashboard with token
                    window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&auth0=true&t=${Date.now()}`;
                } else {
                    alert('You need to be logged in to access the dashboard.');
                }
            } catch (error) {
                console.error('Error accessing dashboard:', error);
                alert('Error accessing dashboard. Please try logging in again.');
            }
        });
    }
    
    // Logout button
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', async function() {
            try {
                console.log("Logout button clicked");
                
                // Log out of Auth0
                await auth0Client.logout({
                    returnTo: window.location.origin
                });
                
                // Clear local storage
                localStorage.removeItem('userToken');
                localStorage.removeItem('userName');
                localStorage.removeItem('userEmail');
                
            } catch (error) {
                console.error('Error during logout:', error);
                
                // Fallback logout - just clear localStorage and refresh
                localStorage.removeItem('userToken');
                localStorage.removeItem('userName');
                localStorage.removeItem('userEmail');
                
                window.location.reload();
            }
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
