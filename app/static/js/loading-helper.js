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

// Loading modal functions
function showLoading(message = "Processing your request...", subtext = "Please wait, this may take a moment", showProgress = false) {
    document.getElementById('loadingModalMessage').textContent = message;
    document.getElementById('loadingModalSubtext').textContent = subtext;

    // Handle progress visibility
    const progressContainer = document.getElementById('loadingProgressContainer');
    if (showProgress) {
        progressContainer.classList.remove('d-none');
        // Reset progress bar to 0
        updateProgress(0, 'Starting...');
    } else {
        progressContainer.classList.add('d-none');
    }

    const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
    loadingModal.show();
}

function hideLoading() {
    const loadingModalEl = document.getElementById('loadingModal');
    const loadingModal = bootstrap.Modal.getInstance(loadingModalEl);
    if (loadingModal) {
        loadingModal.hide();

        // Reset progress bar
        setTimeout(() => {
            const progressContainer = document.getElementById('loadingProgressContainer');
            progressContainer.classList.add('d-none');
            updateProgress(0, '');
        }, 300);
    }
}

// Function to update progress bar
function updateProgress(percent, statusText = '') {
    const progressBar = document.getElementById('loadingProgressBar');
    const progressText = document.getElementById('loadingProgressText');

    // Update progress bar
    percent = Math.min(Math.max(percent, 0), 100); // Ensure value is between 0-100
    const roundedPercent = Math.round(percent);

    progressBar.style.width = `${roundedPercent}%`;
    progressBar.setAttribute('aria-valuenow', roundedPercent);
    progressBar.textContent = `${roundedPercent}%`;

    // Update status text if provided
    if (statusText) {
        progressText.textContent = statusText;
    }
}

// Function to fetch progress updates
let progressCheckInterval = null;

function startProgressCheck(operationId, onComplete = null) {
    // Clear any existing interval
    if (progressCheckInterval) {
        clearInterval(progressCheckInterval);
    }

    const checkProgress = async () => {
        try {
            // Updated URL path to match the blueprint's route
            const response = await fetch(`/spotify/progress/${operationId}`);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            const data = await response.json();

            // Update progress bar
            updateProgress(
                data.percent,
                `${data.completed} of ${data.total} items (${data.status})`
            );

            // Check if operation is complete
            if (data.complete) {
                clearInterval(progressCheckInterval);
                if (onComplete && typeof onComplete === 'function') {
                    onComplete(data);
                }
            }
        } catch (error) {
            console.error("Error checking progress:", error);
        }
    };

    // Start checking immediately
    checkProgress();

    // Then check every 1 second
    progressCheckInterval = setInterval(checkProgress, 1000);

    return {
        stop: () => {
            if (progressCheckInterval) {
                clearInterval(progressCheckInterval);
                progressCheckInterval = null;
            }
        }
    };
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
                const showProgress = this.getAttribute('data-loading-show-progress') === 'true';
                const operationId = this.getAttribute('data-loading-operation-id');

                showLoading(message, subtext, showProgress);

                // If an operation ID is provided, start checking progress
                if (showProgress && operationId) {
                    startProgressCheck(operationId);
                }
            }
        });
    });

    // Handle form submissions with loading
    document.querySelectorAll('form[data-loading="true"]').forEach(form => {
        form.addEventListener('submit', function(e) {
            const message = this.getAttribute('data-loading-message') || "Processing your request...";
            const subtext = this.getAttribute('data-loading-subtext') || "Please wait, this may take a moment";
            const showProgress = this.getAttribute('data-loading-show-progress') === 'true';
            const operationId = this.getAttribute('data-loading-operation-id');

            showLoading(message, subtext, showProgress);

            // If an operation ID is provided, start checking progress
            if (showProgress && operationId) {
                startProgressCheck(operationId);
            }
            // Form will submit normally
        });
    });

    // Handle links with data-loading="true"
    document.querySelectorAll('a[data-loading="true"]').forEach(link => {
        link.addEventListener('click', function(e) {
            const message = this.getAttribute('data-loading-message') || "Processing your request...";
            const subtext = this.getAttribute('data-loading-subtext') || "Please wait, this may take a moment";
            const showProgress = this.getAttribute('data-loading-show-progress') === 'true';
            const operationId = this.getAttribute('data-loading-operation-id');

            showLoading(message, subtext, showProgress);

            // If an operation ID is provided, start checking progress
            if (showProgress && operationId) {
                startProgressCheck(operationId);
            }
        });
    });

    // Auto-hide loading when page is fully loaded
    window.addEventListener('load', function() {
        hideLoading();
    });
});

// Function to add loading behavior to forms that use AJAX
function setupAjaxFormWithLoading(formSelector, submitCallback, loadingMessage = "Processing form...", loadingSubtext = "Please wait", showProgress = false, operationId = null) {
    const form = document.querySelector(formSelector);
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        try {
            showLoading(loadingMessage, loadingSubtext, showProgress);

            // If an operation ID is provided, start checking progress
            let progressChecker = null;
            if (showProgress && operationId) {
                progressChecker = startProgressCheck(operationId);
            }

            await submitCallback(form);

            // Stop progress checking if it was started
            if (progressChecker) {
                progressChecker.stop();
            }
        } catch (error) {
            console.error("Form submission error:", error);
        } finally {
            hideLoading();
        }
    });
}
