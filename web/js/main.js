// main.js - Core functionality for Sanctus Videre HTML service
document.addEventListener('DOMContentLoaded', function() {
    // Initialize user state
    checkUserState();
    
    // Form event listeners
    setupLoginForm();
    setupReviewForm();
    
    // Button event listeners
    setupNavigationButtons();
    
    // Setup direct dashboard access
    setupDirectAccess();
    
    // Initialize Auth0 if enabled
    initAuth0IfEnabled();
});

// Auth0 configuration - You'll update these values when setting up Auth0
const AUTH0_CONFIG = {
    domain: 'your-domain.auth0.com',
    clientId: 'your-client-id',
    redirectUri: window.location.origin,
    audience: 'https://your-api-identifier',
    responseType: 'token id_token',
    scope: 'openid profile email'
};

// Flag to control which authentication method to use
// Set this to true when you're ready to switch to Auth0
let useAuth0 = localStorage.getItem('useAuth0') === 'true';

// Auth0 client instance
let auth0Client = null;

// Predefined test user accounts
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

// Initialize Auth0 if enabled
function initAuth0IfEnabled() {
    if (!useAuth0) return; // Skip if not using Auth0
    
    // This will be implemented when you're ready to activate Auth0
    // We'll load the Auth0 SDK and initialize it here
    console.log("Auth0 would be initialized here when enabled");
    
    // Check if we're returning from an Auth0 redirect
    if (window.location.hash && window.location.hash.includes('access_token')) {
        console.log("Auth0 redirect detected, would process tokens here");
        // We'll handle the Auth0 callback here when implemented
    }
}

// User state management
function checkUserState() {
    // For Auth0 (will be used later)
    if (useAuth0) {
        console.log("Would check Auth0 state here");
        // We'll check Auth0 authentication state here when implemented
        // For now, fall back to original implementation
    }
    
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

// Check if an email is one of our test users
function isTestUser(email) {
    return TEST_USERS.some(user => user.email === email);
}

// Validate test user credentials
function validateTestUser(email, password) {
    return TEST_USERS.some(user => user.email === email && user.password === password);
}

// Login functionality
function setupLoginForm() {
    const loginForm = document.getElementById('login');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // If using Auth0, handle differently
            if (useAuth0) {
                console.log("Would use Auth0 login here");
                // We'll implement Auth0 login here when ready
                // For now, fall back to original implementation
            }
            
            // Original implementation
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
                
                // Regular user login (future Auth0 integration)
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
        createAccountLink.addEventListener('click', function(e) {
            e.preventDefault();
            
            // If using Auth0, handle differently
            if (useAuth0) {
                console.log("Would redirect to Auth0 signup here");
                // We'll implement Auth0 signup here when ready
                // For now, fall back to original implementation
            }
            
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
    console.log("Direct access link element:", directAccessLink); // Debug line
    
    if (directAccessLink) {
        directAccessLink.addEventListener('click', function(e) {
            console.log("Direct access link clicked"); // Debug line
            e.preventDefault();
            
            // Call the simpler function
            accessDashboard();
        });
    } else {
        console.log("Direct access link not found in the document"); // Debug line
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

// Navigation buttons
function setupNavigationButtons() {
    // Dashboard button - add token to URL for Streamlit authentication
    const dashboardButton = document.querySelector('.dashboard-button');
    if (dashboardButton) {
        dashboardButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // If using Auth0, handle differently
            if (useAuth0) {
                console.log("Would use Auth0 tokens for navigation here");
                // We'll implement Auth0 token usage here when ready
                // For now, fall back to original implementation
            }
            
            // Original implementation
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
        logoutButton.addEventListener('click', function() {
            // If using Auth0, handle differently
            if (useAuth0) {
                console.log("Would use Auth0 logout here");
                // We'll implement Auth0 logout here when ready
                // For now, fall back to original implementation
            }
            
            // Original implementation
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

// Toggle Auth0 functionality for testing (will be removed in production)
function toggleAuth0() {
    useAuth0 = !useAuth0;
    localStorage.setItem('useAuth0', useAuth0);
    alert(`Auth0 integration is now ${useAuth0 ? 'ENABLED' : 'DISABLED'}`);
    window.location.reload();
}

// Add a hidden function to enable/disable Auth0 for testing
// You can call this from the browser console with toggleAuth0()
window.toggleAuth0 = toggleAuth0;
