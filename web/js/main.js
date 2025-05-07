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
});

// User state management
function checkUserState() {
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

// Login functionality
function setupLoginForm() {
    const loginForm = document.getElementById('login');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Get form values
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            // Simple validation
            if (email && password) {
                // Create a demo token
                const demoToken = 'demo-token-' + Date.now();
                
                // Store auth info in localStorage
                localStorage.setItem('userToken', demoToken);
                localStorage.setItem('userName', email.split('@')[0]);
                
                // Update UI
                checkUserState();
                
                // Check if admin access or test user
                if (password === 'admin123') { // Your existing admin password
                    localStorage.setItem('isAdmin', 'true');
                    // Admin gets normal URL (existing setup)
                    window.location.href = 'https://ui-production-b574.up.railway.app';
                } 
                // Test user case
                else if (email === 'test@example.com' && password === 'testuser123') {
                    // Store a flag to identify test user
                    localStorage.setItem('isTestUser', 'true');
                    // Redirect test user to fresh AI system - Force clear URL cache
                    window.location.href = 'https://ui-production-b574.up.railway.app?user=new&t=' + Date.now();
                }
                else {
                    // Regular users get normal URL for now
                    window.location.href = 'https://ui-production-b574.up.railway.app';
                }
            }
        });
    }
    
    // Account creation link
    const createAccountLink = document.getElementById('create-account-link');
    if (createAccountLink) {
        createAccountLink.addEventListener('click', function(e) {
            e.preventDefault();
            alert('Account creation would be implemented here in the full version. For testing, use test@example.com with password testuser123.');
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
        window.location.href = 'https://web-production-044b.up.railway.app';
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
            
            // Get user token
            const userToken = localStorage.getItem('userToken');
            const userName = localStorage.getItem('userName');
            const isAdmin = localStorage.getItem('isAdmin');
            const isTestUser = localStorage.getItem('isTestUser') === 'true';
            
            // Create URL with auth parameters
            let dashboardUrl = this.getAttribute('href');
            dashboardUrl += dashboardUrl.includes('?') ? '&' : '?';
            
            // Special handling for test user
            if (isTestUser || userName === 'test') {
                dashboardUrl += `token=${userToken}&user=new&t=${Date.now()}`;
            } else {
                dashboardUrl += `token=${userToken}&user=${userName}`;
            }
            
            // Add admin flag if present
            if (isAdmin === 'true') {
                dashboardUrl += '&admin=true';
            }
            
            // Navigate to dashboard
            window.location.href = dashboardUrl;
        });
    }
    
    // Logout button
    const logoutButton = document.getElementById('logout-button');
    if (logoutButton) {
        logoutButton.addEventListener('click', function() {
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
