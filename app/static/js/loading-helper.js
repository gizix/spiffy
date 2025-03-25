// Show loading modal for fetch/AJAX requests
async function fetchWithLoading(url, options = {}, loadingMessage = "Loading data...", loadingSubtext = "Please wait") {
    try {
        showLoading(loadingMessage, loadingSubtext);
        const response = await fetch(url, options);

        // Check if the response is OK
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error("Fetch error:", error);
        throw error;
    } finally {
        hideLoading();
    }
}

// Create an event that gets triggered when page navigation starts
document.addEventListener('DOMContentLoaded', function() {
    // Handle all links with data-loading-on-navigate="true"
    document.querySelectorAll('[data-loading-on-navigate="true"]').forEach(link => {
        link.addEventListener('click', function(e) {
            // Only show loading if the link is going to navigate away
            // (i.e., it's not prevented by other event handlers)
            if (!e.defaultPrevented) {
                const message = this.getAttribute('data-loading-message') || "Loading page...";
                const subtext = this.getAttribute('data-loading-subtext') || "Please wait while we prepare the next page";
                showLoading(message, subtext);
            }
        });
    });

    // Auto-hide loading when page is fully loaded
    window.addEventListener('load', function() {
        hideLoading();
    });
});

// Function to add loading behavior to forms that use AJAX
function setupAjaxFormWithLoading(formSelector, submitCallback, loadingMessage = "Processing form...", loadingSubtext = "Please wait") {
    const form = document.querySelector(formSelector);
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        try {
            showLoading(loadingMessage, loadingSubtext);
            await submitCallback(form);
        } catch (error) {
            console.error("Form submission error:", error);
        } finally {
            hideLoading();
        }
    });
}
