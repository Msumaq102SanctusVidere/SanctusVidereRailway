// main.js - Core functionality for Sanctus Videre HTML service with Auth0 integration
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Auth0 first
    initAuth0();
    
    // Other event listeners will be set up after authentication state is checked
    setupReviewForm();
    setupDirectAccess();
});

// Auth0 configuration - Updated with your actual values
const AUTH0_CONFIG = {
    domain: 'dev-wl2dxopsswbbvkcb.us.auth0.com',
    client_id: 'BAXPcs4GZAZodDtErS8UxTmugyxbEcZU',
    redirectUri: 'https://sanctusvidere.com/callback.html',
    audience: 'https://your-api-identifier', // Optional - only needed if using an API
    responseType: 'token id_token',
    scope: 'openid profile email'
};

// Flag to control which authentication method to use
// Set this to true to enable Auth0
let useAuth0 = localStorage.getItem('useAuth0') === 'true';

// Auth0 client instance
let auth0Client = null;

// Initialize Auth0
async function initAuth0() {
    try {
        // Only proceed if using Auth0
        if (!useAuth0) {
            console.log("Auth0 is disabled, using original authentication");
            checkUserState();
            setupLoginForm();
            setupNavigationButtons();
            return;
        }
        
        console.log("Initializing Auth0...");
        
        // Check if auth0 is available as a global object
        if (typeof auth0 === 'undefined') {
            console.error("Auth0 SDK not loaded properly!");
            throw new Error("Auth0 SDK not available");
        }
        
        // Create Auth0 client
        auth0Client = await auth0.createAuth0Client({
            domain: AUTH0_CONFIG.domain,
            clientId: AUTH0_CONFIG.clientId,
            redirectUri: AUTH0_CONFIG.redirectUri,
            audience: AUTH0_CONFIG.audience,
            cacheLocation: 'localstorage'
        });
        
        // Check for authentication callback
        if (window.location.search.includes('code=') || 
            window.location.search.includes('error=') ||
            window.location.hash.includes('access_token=')) {
            
            console.log("Auth0 callback detected, handling redirect");
            
            // Handle the redirect
            await auth0Client.handleRedirectCallback();
            
            // Clear the URL
            window.history.replaceState({}, document.title, '/');
        }
        
        // Check if authenticated
        const isAuthenticated = await auth0Client.isAuthenticated();
        
        if (isAuthenticated) {
            console.log("User is authenticated with Auth0");
            
            // Get user info
            const user = await auth0Client.getUser();
            
            // Store user info in localStorage for easy access
            localStorage.setItem('userToken', await auth0Client.getTokenSilently());
            localStorage.setItem('userName', user.name || user.email.split('@')[0]);
            localStorage.setItem('userEmail', user.email);
            
            // Update UI
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('dashboard-access').style.display = 'block';
            document.getElementById('user-name').textContent = user.name || user.email.split('@')[0];
        } else {
            console.log("User is not authenticated with Auth0");
            
            // Show login form
            document.getElementById('login-form').style.display = 'block';
            document.getElementById('dashboard-access').style.display = 'none';
        }
        
        // Set up event listeners
        setupLoginForm();
        setupNavigationButtons();
        
    } catch (error) {
        console.error('Error initializing Auth0:', error);
        
        // Fall back to original implementation
        useAuth0 = false;
        localStorage.setItem('useAuth0', 'false');
        
        checkUserState();
        setupLoginForm();
        setupNavigationButtons();
    }
}

// Original user state management (fallback if Auth0 is disabled)
function checkUserState() {
    // Original implementation
    const userToken = localStorage.getItem('userToken');
    const userName = localStorage.getItem('userName');
    
    if (userToken && userName) {
        // User is logged in, show dashboard access
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('dashboard-access').style.display = 'block';
        document.getElementById('user-name').textContent = userName;
    } else {
        // User is not logged in, show login form
        document.getElementById('login-form').style.display = 'block';
        document.getElementById('dashboard-access').style.display = 'none';
    }
}

// Predefined test user accounts (keep for backward compatibility)
const TEST_USERS = [
    { email: 'test1@example.com', password: 'testuser123', name: 'Test User 1' },
    { email: 'test2@example.com', password: 'testuser123', name: 'Test User 2' },
    { email: 'test3@example.com', password: 'testuser123', name: 'Test User 3' },
    { email: 'test4@example.com', password: 'testuser123', name: 'Test User 4' },
    { email: 'test5@example.com', password: 'testuser123', name: 'Test User 5' },
    { email: 'test6@example.com', password: 'testuser123', name: 'Test User 6' },
    { email: 'test7@example.com', password: 'testuser123', name: 'Test User 7' },
    { email: 'test8@example.com', password: 'testuser123', name: 'Test User 8' },
    { email: 'test9@example.com', password: 'testuser123', name: 'Test User 9' },
    { email: 'test10@example.com', password: 'testuser123', name: 'Test User 10' }
];

// Validate test user credentials (for backward compatibility)
function validateTestUser(email, password) {
    return TEST_USERS.some(user => user.email === email && user.password === password);
}

// Login functionality
function setupLoginForm() {
    const loginForm = document.getElementById('login');
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // If using Auth0, handle login with Auth0
            if (useAuth0) {
                try {
                    console.log("Using Auth0 for login");
                    
                    // Redirect to Auth0 login page
                    await auth0Client.loginWithRedirect({
                        redirect_uri: AUTH0_CONFIG.redirectUri
                    });
                    
                    // The page will redirect to Auth0, so code after this point won't execute
                } catch (error) {
                    console.error('Error during Auth0 login:', error);
                    alert('Login error. Please try again.');
                }
                
                return;
            }
            
            // Original implementation (if Auth0 is disabled)
            console.log("Using original login mechanism");
            
            // Get form values
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            // Simple validation
            if (email && password) {
                // Create a demo token with user identifier
                const userId = email.split('@')[0];
                const demoToken = `user-${userId}-${Date.now()}`;
                
                // Check if admin access
                if (password === 'admin123') { 
                    // Admin gets special privileges
                    localStorage.setItem('isAdmin', 'true');
                    localStorage.setItem('userToken', demoToken);
                    localStorage.setItem('userName', userId);
                    
                    // Admin gets normal URL (existing setup without fresh workspace)
                    window.location.href = 'https://ui-production-b574.up.railway.app';
                    return;
                }
                
                // Check if this is one of our test users
                if (validateTestUser(email, password)) {
                    // Store test user info
                    localStorage.setItem('isTestUser', 'true');
                    localStorage.setItem('userToken', demoToken);
                    localStorage.setItem('userName', userId);
                    
                    // Update UI
                    checkUserState();
                    
                    // Redirect test user to Streamlit frontend with fresh workspace
                    window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${demoToken}&t=${Date.now()}`;
                    return;
                }
                
                // Regular user login
                localStorage.setItem('userToken', demoToken);
                localStorage.setItem('userName', userId);
                
                // Update UI
                checkUserState();
                
                // Give regular users a fresh workspace too
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${demoToken}&t=${Date.now()}`;
            }
        });
    }
    
    // Account creation link
    const createAccountLink = document.getElementById('create-account-link');
    if (createAccountLink) {
        createAccountLink.addEventListener('click', async function(e) {
            e.preventDefault();
            
            // If using Auth0, redirect to signup page
            if (useAuth0) {
                try {
                    console.log("Using Auth0 for signup");
                    
                    // Redirect to Auth0 signup page
                    await auth0Client.loginWithRedirect({
                        redirect_uri: AUTH0_CONFIG.redirectUri,
                        screen_hint: 'signup'
                    });
                    
                    // The page will redirect to Auth0, so code after this point won't execute
                } catch (error) {
                    console.error('Error during Auth0 signup:', error);
                    alert('Signup error. Please try again.');
                }
                
                return;
            }
            
            // Original implementation (if Auth0 is disabled)
            // Show test user information
            const testUserInfo = TEST_USERS.map(user => `${user.email}: password = ${user.password}`).join('\n');
            alert(`Account creation will be implemented with Auth0 in the full version.\n\nFor testing, you can use one of these test accounts:\n\n${testUserInfo}`);
        });
    }
    
    // Admin access link
    const adminLink = document.getElementById('admin-link');
    if (adminLink) {
        adminLink.addEventListener('click', function(e) {
            e.preventDefault();
            const adminCode = prompt('Enter admin access code:');
            if (adminCode === 'admin123') { // Simple demo code
                localStorage.setItem('isAdmin', 'true');
                alert('Admin access granted. You now have access to all features.');
            }
        });
    }
}

// Navigation buttons
function setupNavigationButtons() {
    // Dashboard button - add token to URL for Streamlit authentication
    const dashboardButton = document.querySelector('.dashboard-button');
    if (dashboardButton) {
        dashboardButton.addEventListener('click', async function(e) {
            e.preventDefault();
            
            // If using Auth0, use Auth0 token
            if (useAuth0) {
                try {
                    console.log("Using Auth0 token for dashboard access");
                    
                    // Get token and user info
                    const token = await auth0Client.getTokenSilently();
                    const user = await auth0Client.getUser();
                    const userId = user.sub || user.email.split('@')[0];
                    
                    // Redirect to dashboard with token
                    window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userId}&token=${token}&auth0=true&t=${Date.now()}`;
                } catch (error) {
                    console.error('Error getting Auth0 token:', error);
                    alert('Error accessing dashboard. Please try logging in again.');
                }
                
                return;
            }
            
            // Original implementation
            console.log("Using original token for dashboard access");
            
            // Get user info
            const userToken = localStorage.getItem('userToken');
            const userName = localStorage.getItem('userName');
            const isAdmin = localStorage.getItem('isAdmin') === 'true';
            
            if (isAdmin) {
                // Admin users go to admin dashboard
                window.location.href = 'https://ui-production-b574.up.railway.app';
            } else {
                // All other users (test and regular) get their own workspace
                window.location.href = `https://app.sanctusvidere.com?user=new&userid=${userName}&token=${userToken}&t=${Date.now()}`;
            }
        });
    }
    
    // Logout button
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', async function() {
            // If using Auth0, use Auth0 logout
            if (useAuth0) {
                try {
                    console.log("Using Auth0 for logout");
                    
                    // Log out of Auth0
                    await auth0Client.logout({
                        returnTo: window.location.origin
                    });
                    
                    // Clear local storage (Auth0 will also redirect the page)
                    localStorage.removeItem('userToken');
                    localStorage.removeItem('userName');
                    localStorage.removeItem('userEmail');
                    localStorage.removeItem('isAdmin');
                    localStorage.removeItem('isTestUser');
                } catch (error) {
                    console.error('Error during Auth0 logout:', error);
                    
                    // Fall back to original logout
                    localStorage.removeItem('userToken');
                    localStorage.removeItem('userName');
                    localStorage.removeItem('isAdmin');
                    localStorage.removeItem('isTestUser');
                    
                    // Update UI
                    checkUserState();
                }
                
                return;
            }
            
            // Original implementation
            console.log("Using original logout mechanism");
            
            // Clear auth data
            localStorage.removeItem('userToken');
            localStorage.removeItem('userName');
            localStorage.removeItem('isAdmin');
            localStorage.removeItem('isTestUser');
            
            // Update UI
            checkUserState();
        });
    }
}

// Direct dashboard access function - simplified approach
function accessDashboard() {
    const accessCode = prompt('Enter direct access code:');
    if (accessCode === 'sanctus2025') {
        window.location.href = 'https://app.sanctusvidere.com';
    } else {
        alert('Invalid access code.');
    }
}

// Setup direct dashboard access link in footer
function setupDirectAccess() {
    const directAccessLink = document.getElementById('admin-access-direct');
    console.log("Direct access link element:", directAccessLink);
    
    if (directAccessLink) {
        directAccessLink.addEventListener('click', function(e) {
            console.log("Direct access link clicked");
            e.preventDefault();
            
            // Call the simpler function
            accessDashboard();
        });
    } else {
        console.log("Direct access link not found in the document");
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

// Toggle Auth0 functionality for testing (will be removed in production)
function toggleAuth0() {
    useAuth0 = !useAuth0;
    localStorage.setItem('useAuth0', useAuth0.toString());
    alert(`Auth0 integration is now ${useAuth0 ? 'ENABLED' : 'DISABLED'}`);
    window.location.reload();
}

// Add a hidden function to enable/disable Auth0 for testing
// You can call this from the browser console with toggleAuth0()
window.toggleAuth0 = toggleAuth0;
