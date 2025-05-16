// MAIN.JS DEBUG - Direct variable
console.log("Main.js loading directly");

// Auth0 Lock widget
let lock = null;

// Auth0 configuration
const AUTH0_CONFIG = {
    domain: "dev-wl2dxopsswbbvkcb.us.auth0.com",
    clientId: "BAXPcs4GZAZodDtErS0UxTmugyxbEcZU",
    mainUrl: "https://sanctusvidere.com",
    appUrl: "https://app.sanctusvidere.com"
};

// Stripe configuration - MULTIPLE PAYMENT OPTIONS
const STRIPE_CONFIG = {
    paymentLinks: {
        daily: "https://buy.stripe.com/7sY8wQ8QK8OFfi7cUP3gk01", // Daily Subscription link
        weekly: "https://buy.stripe.com/6oU9AUd702qh0nddYT3gk02", // Weekly Subscription link
        monthly: "https://buy.stripe.com/cN2aFI9XK2r2gAofYY" // Monthly Subscription link
    },
    testAccounts: ["test2@example.com"] // Your test account that bypasses payment
};

// Direct login button handler - outside any event for reliability
console.log("Setting up direct login button handler");
function setupLoginButtonDirect() {
    console.log("Direct setup function running");
    const loginButton = document.getElementById('login-button');
    console.log("Direct login button check:", loginButton);
    
    if (loginButton) {
        console.log("Adding direct click handler to login button");
        loginButton.addEventListener('click', function() {
            console.log("Login button clicked directly!");
            window.location.href = 'plans.html';
        });
    } else {
        console.log("Login button not found in direct setup");
    }
}

// Call it after a short delay to ensure DOM is ready
setTimeout(setupLoginButtonDirect, 500);

// Also try the standard way
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM Content Loaded Event");
    setupLoginButtonDirect();
});

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
        
        // Detect and fix URL format if needed
        fixUrlFormat();
        
        // Handle successful payment return
        handlePaymentReturn();
    } catch (err) {
        console.error("Error during initialization:", err.message);
    }
    
    // Set up other components
    setupReviewForm();
    setupDirectAccess();
});

// Check and fix URL format if needed
function fixUrlFormat() {
    // Check if we're on the app page with the wrong parameter format
    if (window.location.href.includes('app.sanctusvidere.com') && 
        window.location.href.includes('user=')) {
        
        console.log("Detected old URL format, attempting to fix...");
        
        // Get the token from the URL
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        
        // Create a consistent user ID based on the token (if available)
        let userId = 'user-';
        if (token) {
            // Use part of the token to create a consistent ID
            userId += token.substring(0, 10).replace(/[^a-zA-Z0-9]/g, '');
        } else {
            // Fallback to timestamp if no token
            userId += Date.now();
        }
        
        // Create and navigate to the correct URL
        const correctUrl = `${window.location.origin}?user_id=${encodeURIComponent(userId)}&token=${token || ''}`;
        console.log("Redirecting to correct URL format:", correctUrl);
        window.location.replace(correctUrl);
    }
}

// Handle return from payment
function handlePaymentReturn() {
    const urlParams = new URLSearchParams(window.location.search);
    
    // Check if this is a return from payment (Stripe will add parameters to the URL)
    if (urlParams.has('payment_status')) {
        const paymentStatus = urlParams.get('payment_status');
        
        if (paymentStatus === 'success' || paymentStatus === 'paid') {
            console.log("Payment successful, setting subscription status");
            
            // Store subscription status
            localStorage.setItem('subscription_active', 'true');
            localStorage.setItem('subscription_date', Date.now().toString());
            
            // Store plan information if available
            const plan = urlParams.get('plan');
            if (plan) {
                localStorage.setItem('subscription_plan', plan);
            }
            
            // Clean up URL
            const newUrl = window.location.pathname;
            window.history.replaceState({}, document.title, newUrl);
        }
    }
}

// Check if user is a test account or has subscription
function isSubscribed(email) {
    // Test accounts automatically bypass payment
    if (STRIPE_CONFIG.testAccounts.includes(email)) {
        console.log("Test account detected, bypassing subscription check");
        return true;
    }
    
    // Check local storage for subscription status
    const hasSubscription = localStorage.getItem('subscription_active') === 'true';
    return hasSubscription;
}

// Redirect to Stripe payment link
function redirectToPayment(email, userId, plan = 'monthly') {
    // Get the correct payment link based on the plan
    const paymentLink = STRIPE_CONFIG.paymentLinks[plan];
    
    // Construct the payment link with success/cancel URLs
    const successUrl = encodeURIComponent(`${AUTH0_CONFIG.appUrl}?payment_status=success&user_id=${userId}&plan=${plan}`);
    const cancelUrl = encodeURIComponent(AUTH0_CONFIG.mainUrl);
    
    // Create the full URL with parameters
    let paymentUrl = paymentLink;
    
    // Add client_reference_id if the link doesn't have parameters yet
    if (!paymentUrl.includes('?')) {
        paymentUrl += `?client_reference_id=${userId}`;
    } else {
        paymentUrl += `&client_reference_id=${userId}`;
    }
    
    // Add success and cancel URLs
    paymentUrl += `&success_url=${successUrl}&cancel_url=${cancelUrl}`;
    
    // Redirect to payment
    console.log(`Redirecting to ${plan} payment:`, paymentUrl);
    window.location.href = paymentUrl;
}

// Setup login button on logged-out page
function setupLoginButton() {
    const loginButton = document.getElementById('login-again-button');
    if (loginButton) {
        loginButton.addEventListener('click', function() {
            login();
        });
    }
}

// Initialize Auth0 Lock with minimal styling
function initializeLock() {
    // Minimal configuration - just changing the title and primary color
    lock = new Auth0Lock(AUTH0_CONFIG.clientId, AUTH0_CONFIG.domain, {
        auth: {
            redirectUrl: AUTH0_CONFIG.mainUrl,
            responseType: 'token id_token',
            params: {
                scope: 'openid profile email'
            }
        },
        theme: {
            primaryColor: '#5956E9'  // Purple color matching your third image
        },
        languageDictionary: {
            title: 'Sanctus Videre'  // Custom title
        },
        autoclose: true,
        closable: true,
        avatar: null  // Disable Gravatar
    });
    
    // Set up the authenticated event handler
    lock.on('authenticated', function(authResult) {
        // Get the tokens from the authResult
        const idToken = authResult.idToken;
        const accessToken = authResult.accessToken;
        
        // Store tokens securely (standard practice)
        localStorage.setItem('auth_id_token', idToken);
        localStorage.setItem('auth_access_token', accessToken);
        
        // Get user profile
        lock.getUserInfo(accessToken, function(error, profile) {
            if (error) {
                console.error("Error getting user info:", error);
                
                // Create a user ID from the token instead
                const userId = 'user-' + idToken.substring(0, 10).replace(/[^a-zA-Z0-9]/g, '');
                const redirectUrl = `${AUTH0_CONFIG.appUrl}?user_id=${encodeURIComponent(userId)}&token=${encodeURIComponent(idToken)}`;
                console.log(`Redirecting with token-based user_id:`, redirectUrl);
                window.location.replace(redirectUrl);
                return;
            }
            
            // Get user ID and email
            const userId = profile.sub || profile.user_id || 'user-' + Date.now();
            const userEmail = profile.email || '';
            console.log("Authenticated user:", userId, userEmail);
            
            // Store user info (standard practice)
            localStorage.setItem('auth_user_id', userId);
            if (profile.name) localStorage.setItem('auth_user_name', profile.name);
            if (profile.email) localStorage.setItem('auth_user_email', profile.email);
            localStorage.setItem('auth_login_time', Date.now().toString());
            
            // Check if user is subscribed or is a test account
            if (isSubscribed(userEmail)) {
                // User has subscription, redirect to app
                const appUrl = `${AUTH0_CONFIG.appUrl}?user_id=${encodeURIComponent(userId)}&token=${encodeURIComponent(idToken)}`;
                console.log(`User has subscription, redirecting to app:`, appUrl);
                window.location.replace(appUrl);
            } else {
                // User needs to subscribe, redirect to plans page
                console.log(`User needs subscription, redirecting to plans page`);
                window.location.href = `${AUTH0_CONFIG.mainUrl}/plans.html?user_id=${encodeURIComponent(userId)}`;
            }
        });
    });
    
    console.log("Auth0 Lock initialized with minimal styling");
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

// Logout function - Using standard practices
function logout() {
    // Clear auth data but preserve user ID to remember this user has logged in before
    clearAuthData(false); // false = don't clear user ID
    
    // Use Auth0's official logout endpoint (most reliable method)
    const returnTo = encodeURIComponent(window.location.origin + '/logged-out.html');
    window.location.href = `https://${AUTH0_CONFIG.domain}/v2/logout?client_id=${AUTH0_CONFIG.clientId}&returnTo=${returnTo}`;
    
    return false;
}

// Helper function to clear auth data using standard practices
function clearAuthData(clearUserID = true) {
    // Clear auth tokens
    localStorage.removeItem('auth_id_token');
    localStorage.removeItem('auth_access_token');
    
    // Optionally clear user identity info
    if (clearUserID) {
        localStorage.removeItem('auth_user_id');
        localStorage.removeItem('auth_user_name');
        localStorage.removeItem('auth_user_email');
    }
    
    localStorage.removeItem('auth_login_time');
    
    // Clear any Auth0 specific items
    localStorage.removeItem('auth0.is.authenticated');
    
    // Find and clear any Auth0-related items
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.includes('auth0') || key.includes('Auth0'))) {
            localStorage.removeItem(key);
        }
    }
    
    // Clear subscription data (if logging out completely)
    if (clearUserID) {
        localStorage.removeItem('subscription_active');
        localStorage.removeItem('subscription_date');
        localStorage.removeItem('subscription_plan');
    }
    
    // Clear session storage too (standard security practice)
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
    const userName = localStorage.getItem('auth_user_name') || 'Anonymous User';
    
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
