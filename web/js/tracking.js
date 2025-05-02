// tracking.js - Simple client-side analytics for Sanctus Videre
(function() {
    // Initialize tracking on page load
    initTracking();
    
    // Basic tracking initialization
    function initTracking() {
        // Create or retrieve user identifier
        const trackingId = getUserTrackingId();
        
        // Track page view
        trackEvent('page_view', {
            page: window.location.pathname,
            referrer: document.referrer
        });
        
        // Add click tracking to important elements
        setupClickTracking();
        
        // Track time on site when leaving
        window.addEventListener('beforeunload', function() {
            const timeOnSite = Math.round((Date.now() - window.performance.timing.navigationStart) / 1000);
            trackEvent('session_end', {
                duration: timeOnSite
            });
        });
    }
    
    // Get or create user tracking ID
    function getUserTrackingId() {
        let trackingId = localStorage.getItem('sv_tracking_id');
        
        if (!trackingId) {
            // Generate a simple ID if none exists
            trackingId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('sv_tracking_id', trackingId);
        }
        
        return trackingId;
    }
    
    // Setup click tracking for important elements
    function setupClickTracking() {
        // Track button clicks
        document.querySelectorAll('button, .button').forEach(function(button) {
            button.addEventListener('click', function() {
                trackEvent('button_click', {
                    button_text: this.innerText.trim(),
                    button_id: this.id || 'unnamed_button'
                });
            });
        });
        
        // Track dashboard navigation
        const dashboardButton = document.querySelector('.dashboard-button');
        if (dashboardButton) {
            dashboardButton.addEventListener('click', function() {
                trackEvent('dashboard_navigation', {
                    url: this.getAttribute('href')
                });
            });
        }
        
        // Track review form opens
        const reviewButtons = document.querySelectorAll('#review-button, #submit-review-button');
        reviewButtons.forEach(function(button) {
            button.addEventListener('click', function() {
                trackEvent('review_form_open');
            });
        });
    }
    
    // Track a specific event
    function trackEvent(eventName, data = {}) {
        // Get user info
        const trackingId = getUserTrackingId();
        const isLoggedIn = !!localStorage.getItem('userToken');
        const isAdmin = localStorage.getItem('isAdmin') === 'true';
        
        // Build event data
        const eventData = {
            event: eventName,
            trackingId: trackingId,
            timestamp: new Date().toISOString(),
            page: window.location.pathname,
            userAgent: navigator.userAgent,
            isLoggedIn: isLoggedIn,
            isAdmin: isAdmin,
            ...data
        };
        
        // Store in localStorage for demo purposes
        // In production, you would send this to your analytics service
        storeEvent(eventData);
        
        // If Google Analytics or similar is available, you would call it here
        if (window.gtag) {
            window.gtag('event', eventName, data);
        }
        
        return true;
    }
    
    // Store events in localStorage for demo
    function storeEvent(eventData) {
        const events = JSON.parse(localStorage.getItem('sv_analytics') || '[]');
        events.push(eventData);
        
        // Keep only most recent 100 events to avoid storage issues
        if (events.length > 100) {
            events.shift();
        }
        
        localStorage.setItem('sv_analytics', JSON.stringify(events));
    }
    
    // Expose tracking function globally for use in other scripts
    window.trackEvent = trackEvent;
})();
