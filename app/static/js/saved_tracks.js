// Script to preload and process data while showing the loading screen
document.addEventListener('DOMContentLoaded', function() {
    // Add CSS for JSON collapsible sections
    const style = document.createElement('style');
    style.textContent = `
        .json-container {
            max-height: 350px;
            overflow-y: auto;
            background-color: #f8f9fa;
            border-radius: 4px;
            padding: 10px;
        }
        .json-toggle {
            cursor: pointer;
            margin-bottom: 8px;
        }
        .json-toggle i {
            transition: transform 0.2s;
        }
        .json-toggle[aria-expanded="true"] i {
            transform: rotate(180deg);
        }
    `;
    document.head.appendChild(style);

    // Function to update loading progress
    function updateLoadingProgress(percent, status) {
        document.getElementById('loadingProgressBar').style.width = `${percent}%`;
        if (status) {
            document.getElementById('loadingStatus').textContent = status;
        }
    }

    // Process data in chunks to avoid blocking the UI
    function processDataInChunks() {
        updateLoadingProgress(10, "Initializing...");

        // Get all the track data rows - we'll process them in chunks
        const trackRows = document.querySelectorAll('.track-row');
        const totalRows = trackRows.length;

        // If we don't have any tracks, show the main content immediately
        if (totalRows === 0) {
            document.getElementById('initialLoadingContainer').style.display = 'none';
            document.getElementById('mainContent').style.display = 'block';
            return;
        }

        // Process tracks in chunks of 50 to avoid UI freezing
        const chunkSize = 50;
        let processedRows = 0;

        updateLoadingProgress(20, `Processing ${totalRows} tracks...`);

        function processNextChunk() {
            const start = processedRows;
            const end = Math.min(processedRows + chunkSize, totalRows);

            for (let i = start; i < end; i++) {
                // Any per-row preparation could be done here
                processedRows++;
            }

            // Update progress
            const progress = 20 + Math.round(60 * processedRows / totalRows);
            updateLoadingProgress(progress, `Processing tracks (${processedRows}/${totalRows})...`);

            // If there are more rows to process, schedule the next chunk
            if (processedRows < totalRows) {
                setTimeout(processNextChunk, 0);
            } else {
                // All rows processed, now prepare UI elements
                prepareUIElements();
            }
        }

        // Start processing chunks
        setTimeout(processNextChunk, 0);
    }

    function prepareUIElements() {
        updateLoadingProgress(80, "Preparing visualization...");

        // Wait a bit to allow the UI to render the progress
        setTimeout(() => {
            // Prepare any UI elements that need initialization
            updateLoadingProgress(90, "Building charts...");

            // Wait a bit more to show the nearly-complete progress
            setTimeout(() => {
                updateLoadingProgress(100, "Complete!");

                // Small final delay to show the complete state before showing content
                setTimeout(() => {
                    // Hide loading container and show main content
                    document.getElementById('initialLoadingContainer').style.display = 'none';
                    document.getElementById('mainContent').style.display = 'block';

                    // Initialize the main page JS
                    initializeMainFunctionality();
                }, 500);
            }, 300);
        }, 300);
    }

    // Helper function to determine if details should be auto-collapsed
    function shouldAutoCollapse(content) {
        // Count the number of elements that indicate complexity
        const artistCount = (content.match(/<strong>Artists:<\/strong>/g) || []).length;
        const albumCount = (content.match(/<strong>Album:<\/strong>/g) || []).length;
        const tracksCount = (content.match(/<strong>Track Details:<\/strong>/g) || []).length;

        // If any of these counts is large, it's a complex entry
        const totalCount = artistCount + albumCount + tracksCount;
        return totalCount > 5;
    }

    // Initialize everything once data is ready
    function initializeMainFunctionality() {
        // Prepare data for charts
        const tracks = [];
        const artistCounter = {};
        const albumCounter = {};
        const popularityBuckets = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        const years = new Set();

        // Pagination variables
        let currentPage = 1;
        let pageSize = 50; // Default
        let allRows = [];
        let filteredRows = [];

        // Store original details rows for reference
        const detailsContent = {};

        // Table Sorting
        let currentSort = { column: null, direction: 'asc' };

        // Process tracks data
        document.querySelectorAll('.track-row').forEach(row => {
            const track = {
                name: row.getAttribute('data-track'),
                artist: row.getAttribute('data-artist'),
                album: row.getAttribute('data-album'),
                popularity: parseInt(row.getAttribute('data-popularity')) || 0,
                savedAt: row.getAttribute('data-saved-at'),
                releaseDate: row.getAttribute('data-release-date'),
                duration: parseInt(row.getAttribute('data-duration')) || 0
            };

            tracks.push(track);

            // Count artists for pie chart
            if (track.artist) {
                if (artistCounter[track.artist]) {
                    artistCounter[track.artist]++;
                } else {
                    artistCounter[track.artist] = 1;
                }
            }

            // Count albums
            if (track.album) {
                if (albumCounter[track.album]) {
                    albumCounter[track.album]++;
                } else {
                    albumCounter[track.album] = 1;
                }
            }

            // Add to popularity distribution
            const bucketIndex = Math.min(9, Math.floor(track.popularity / 10));
            popularityBuckets[bucketIndex]++;

            // Add release year for filter
            if (track.releaseDate) {
                const year = track.releaseDate.split('-')[0];
                if (year) years.add(year);
            }
        });

        // Initialize pagination
        const pageSizeSelect = document.getElementById('pageSizeSelect');
        pageSizeSelect.addEventListener('change', function() {
            pageSize = parseInt(this.value);
            currentPage = 1; // Reset to first page
            renderTable();
        });

        // Collect all rows for pagination and preserve details
        function collectRows() {
            const table = document.getElementById('tracksTable');
            const tbody = table.querySelector('tbody');

            // Get all regular rows (not detail rows)
            allRows = Array.from(tbody.querySelectorAll('tr:not(.collapse)'));

            // Store original index for each row
            allRows.forEach((row, index) => {
                const originalIndex = row.cells[0].textContent;
                row.setAttribute('data-original-index', originalIndex);

                // Find the details row for this track
                const detailsRow = document.getElementById(`details-${originalIndex}`);
                if (detailsRow) {
                    // Store the inner content of the details row
                    detailsContent[originalIndex] = detailsRow.querySelector('td').innerHTML;
                }
            });

            // Initialize filtered rows
            filteredRows = [...allRows];

            // Initial render
            renderTable();
        }

        // Populate filters
        const artistFilter = document.getElementById('artistFilter');
        const albumFilter = document.getElementById('albumFilter');
        const yearFilter = document.getElementById('yearFilter');
        const popularityFilter = document.getElementById('popularityFilter');
        const popularityValue = document.getElementById('popularityValue');

        // Sort artists by count descending
        const sortedArtists = Object.entries(artistCounter)
            .sort((a, b) => b[1] - a[1])
            .map(entry => entry[0]);

        // Add artists to filter
        sortedArtists.forEach(artist => {
            const option = document.createElement('option');
            option.value = artist;
            option.textContent = artist;
            artistFilter.appendChild(option);
        });

        // Sort albums by count descending
        const sortedAlbums = Object.entries(albumCounter)
            .sort((a, b) => b[1] - a[1])
            .map(entry => entry[0]);

        // Add albums to filter
        sortedAlbums.forEach(album => {
            const option = document.createElement('option');
            option.value = album;
            option.textContent = album;
            albumFilter.appendChild(option);
        });

        // Sort years
        const sortedYears = Array.from(years).sort().reverse();

        // Add years to filter
        sortedYears.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearFilter.appendChild(option);
        });

        // Create popularity distribution chart
        const popularityCtx = document.getElementById('popularityDistribution').getContext('2d');
        const popularityChart = new Chart(popularityCtx, {
            type: 'bar',
            data: {
                labels: ['0-9', '10-19', '20-29', '30-39', '40-49', '50-59', '60-69', '70-79', '80-89', '90-100'],
                datasets: [{
                    label: 'Tracks by Popularity',
                    data: popularityBuckets,
                    backgroundColor: 'rgba(29, 185, 84, 0.6)',
                    borderColor: 'rgba(29, 185, 84, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Tracks'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Popularity Score'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Track Popularity Distribution'
                    }
                }
            }
        });

        // Create top artists chart (only top 5)
        const topArtists = Object.entries(artistCounter)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5);

        const artistsCtx = document.getElementById('artistsChart').getContext('2d');
        const artistsChart = new Chart(artistsCtx, {
            type: 'pie',
            data: {
                labels: topArtists.map(a => a[0]),
                datasets: [{
                    data: topArtists.map(a => a[1]),
                    backgroundColor: [
                        'rgba(29, 185, 84, 0.8)',
                        'rgba(25, 20, 20, 0.8)',
                        'rgba(30, 215, 96, 0.8)',
                        'rgba(45, 70, 185, 0.8)',
                        'rgba(230, 30, 50, 0.8)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                plugins: {
                    title: {
                        display: true,
                        text: 'Your Top 5 Artists'
                    },
                    legend: {
                        position: 'right'
                    }
                }
            }
        });

        document.querySelectorAll('.sortable').forEach(header => {
            header.addEventListener('click', () => {
                const column = header.getAttribute('data-sort');
                let direction = 'asc';

                if (currentSort.column === column) {
                    direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
                }

                sortTable(column, direction);

                // Update sort indicators
                document.querySelectorAll('.sortable i').forEach(icon => {
                    icon.className = 'bi bi-arrow-down-up';
                });

                const icon = header.querySelector('i');
                icon.className = direction === 'asc' ? 'bi bi-arrow-up' : 'bi bi-arrow-down';

                currentSort = { column, direction };
            });
        });

        function sortTable(column, direction) {
            filteredRows.sort((a, b) => {
                let aValue, bValue;

                switch(column) {
                    case 'index':
                        aValue = parseInt(a.cells[0].textContent);
                        bValue = parseInt(b.cells[0].textContent);
                        break;
                    case 'track':
                        aValue = a.cells[1].textContent.toLowerCase();
                        bValue = b.cells[1].textContent.toLowerCase();
                        break;
                    case 'artist':
                        aValue = a.cells[2].textContent.toLowerCase();
                        bValue = b.cells[2].textContent.toLowerCase();
                        break;
                    case 'album':
                        aValue = a.cells[3].textContent.toLowerCase();
                        bValue = b.cells[3].textContent.toLowerCase();
                        break;
                    case 'popularity':
                        aValue = parseInt(a.getAttribute('data-popularity')) || 0;
                        bValue = parseInt(b.getAttribute('data-popularity')) || 0;
                        break;
                    case 'duration':
                        aValue = parseInt(a.getAttribute('data-duration')) || 0;
                        bValue = parseInt(b.getAttribute('data-duration')) || 0;
                        break;
                    case 'saved_at':
                        aValue = a.getAttribute('data-saved-at') || '';
                        bValue = b.getAttribute('data-saved-at') || '';
                        break;
                    default:
                        return 0;
                }

                if (aValue < bValue) return direction === 'asc' ? -1 : 1;
                if (aValue > bValue) return direction === 'asc' ? 1 : -1;
                return 0;
            });

            renderTable();
        }

        function renderTable() {
            const table = document.getElementById('tracksTable');
            const tbody = table.querySelector('tbody');

            // Clear tbody
            while (tbody.firstChild) {
                tbody.removeChild(tbody.firstChild);
            }

            // Calculate pagination
            const totalPages = pageSize === 0 ? 1 : Math.ceil(filteredRows.length / pageSize);
            if (currentPage > totalPages && totalPages > 0) {
                currentPage = totalPages;
            }

            // Get current page rows
            let displayedRows;
            if (pageSize === 0) {
                displayedRows = filteredRows;
            } else {
                const startIndex = (currentPage - 1) * pageSize;
                displayedRows = filteredRows.slice(startIndex, startIndex + pageSize);
            }

            // Update displayed rows info
            document.getElementById('displayedRowsInfo').textContent =
                `Showing ${displayedRows.length} of ${filteredRows.length} tracks`;

            // Repopulate tbody with current page rows and their details rows
            displayedRows.forEach((row, displayIndex) => {
                const originalIndex = row.getAttribute('data-original-index');

                // Clone the row
                const newRow = row.cloneNode(true);

                // Update row number for visual consistency
                const startNumber = pageSize === 0 ? 1 : (currentPage - 1) * pageSize + 1;
                newRow.cells[0].textContent = startNumber + displayIndex;

                // Create a new details ID specific to this page
                const newDetailsID = `details-page-${displayIndex + 1}`;

                // Fix the details button to target the correct collapse element
                const detailsButton = newRow.querySelector('button[data-bs-target]');
                if (detailsButton) {
                    detailsButton.setAttribute('data-bs-target', `#${newDetailsID}`);
                }

                tbody.appendChild(newRow);

                // If we have content for this row's details, create a new details row
                if (detailsContent[originalIndex]) {
                    // Check if this details section should be auto-collapsed
                    const isLargeDetails = shouldAutoCollapse(detailsContent[originalIndex]);

                    // Process the HTML to make the JSON section collapsible
                    const detailsHTML = detailsContent[originalIndex];
                    const processedHTML = detailsHTML.replace(
                        /<h6>Full Data:<\/h6>\s*<pre class="mb-0"><code>(.*?)<\/code><\/pre>/s,
                        `<h6>
                            <button class="btn btn-sm btn-outline-secondary json-toggle" type="button" 
                                data-bs-toggle="collapse" 
                                data-bs-target="#json-${newDetailsID}" 
                                aria-expanded="false">
                                Full Data <i class="bi bi-chevron-down"></i>
                            </button>
                        </h6>
                        <div class="collapse json-container" id="json-${newDetailsID}">
                            <pre class="mb-0"><code>$1</code></pre>
                        </div>`
                    );

                    const newDetailsRow = document.createElement('tr');
                    newDetailsRow.className = 'collapse';
                    newDetailsRow.id = newDetailsID;

                    // Create a cell that spans the entire row
                    const detailsCell = document.createElement('td');
                    detailsCell.setAttribute('colspan', '8');
                    detailsCell.innerHTML = processedHTML;

                    newDetailsRow.appendChild(detailsCell);
                    tbody.appendChild(newDetailsRow);
                }
            });

            // Update pagination controls
            updatePagination(totalPages);
        }

        function updatePagination(totalPages) {
            const container = document.getElementById('paginationContainer');
            container.innerHTML = '';

            // Don't show pagination if showing all or there's only one page
            if (pageSize === 0 || totalPages <= 1) {
                return;
            }

            // Previous button
            const prevLi = document.createElement('li');
            prevLi.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
            const prevLink = document.createElement('a');
            prevLink.className = 'page-link';
            prevLink.href = '#';
            prevLink.innerHTML = '&laquo;';
            prevLink.addEventListener('click', (e) => {
                e.preventDefault();
                if (currentPage > 1) {
                    currentPage--;
                    renderTable();
                }
            });
            prevLi.appendChild(prevLink);
            container.appendChild(prevLi);

            // Page numbers
            const maxVisiblePages = 5;
            let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
            let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

            // Adjust if we're at the end
            if (endPage - startPage + 1 < maxVisiblePages) {
                startPage = Math.max(1, endPage - maxVisiblePages + 1);
            }

            // First page link if needed
            if (startPage > 1) {
                const firstLi = document.createElement('li');
                firstLi.className = 'page-item';
                const firstLink = document.createElement('a');
                firstLink.className = 'page-link';
                firstLink.href = '#';
                firstLink.textContent = '1';
                firstLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    currentPage = 1;
                    renderTable();
                });
                firstLi.appendChild(firstLink);
                container.appendChild(firstLi);

                // Add ellipsis if needed
                if (startPage > 2) {
                    const ellipsisLi = document.createElement('li');
                    ellipsisLi.className = 'page-item disabled';
                    const ellipsisSpan = document.createElement('span');
                    ellipsisSpan.className = 'page-link';
                    ellipsisSpan.innerHTML = '&hellip;';
                    ellipsisLi.appendChild(ellipsisSpan);
                    container.appendChild(ellipsisLi);
                }
            }

            // Page numbers
            for (let i = startPage; i <= endPage; i++) {
                const pageLi = document.createElement('li');
                pageLi.className = `page-item ${i === currentPage ? 'active' : ''}`;
                const pageLink = document.createElement('a');
                pageLink.className = 'page-link';
                pageLink.href = '#';
                pageLink.textContent = i;
                pageLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    currentPage = i;
                    renderTable();
                });
                pageLi.appendChild(pageLink);
                container.appendChild(pageLi);
            }

            // Last page link if needed
            if (endPage < totalPages) {
                // Add ellipsis if needed
                if (endPage < totalPages - 1) {
                    const ellipsisLi = document.createElement('li');
                    ellipsisLi.className = 'page-item disabled';
                    const ellipsisSpan = document.createElement('span');
                    ellipsisSpan.className = 'page-link';
                    ellipsisSpan.innerHTML = '&hellip;';
                    ellipsisLi.appendChild(ellipsisSpan);
                    container.appendChild(ellipsisLi);
                }

                const lastLi = document.createElement('li');
                lastLi.className = 'page-item';
                const lastLink = document.createElement('a');
                lastLink.className = 'page-link';
                lastLink.href = '#';
                lastLink.textContent = totalPages;
                lastLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    currentPage = totalPages;
                    renderTable();
                });
                lastLi.appendChild(lastLink);
                container.appendChild(lastLi);
            }

            // Next button
            const nextLi = document.createElement('li');
            nextLi.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;
            const nextLink = document.createElement('a');
            nextLink.className = 'page-link';
            nextLink.href = '#';
            nextLink.innerHTML = '&raquo;';
            nextLink.addEventListener('click', (e) => {
                e.preventDefault();
                if (currentPage < totalPages) {
                    currentPage++;
                    renderTable();
                }
            });
            nextLi.appendChild(nextLink);
            container.appendChild(nextLi);
        }

        // Search and Filtering
        const searchInput = document.getElementById('searchInput');
        const searchButton = document.getElementById('searchButton');
        const toggleFilters = document.getElementById('toggleFilters');
        const filtersContainer = document.getElementById('filtersContainer');
        const resetFilters = document.getElementById('resetFilters');

        // Toggle filters container
        toggleFilters.addEventListener('click', () => {
            const filtersCollapse = new bootstrap.Collapse(filtersContainer);
            filtersCollapse.toggle();
        });

        // Update popularity value display
        popularityFilter.addEventListener('input', () => {
            popularityValue.textContent = popularityFilter.value;
            applyFilters();
        });

        // Reset filters
        resetFilters.addEventListener('click', () => {
            artistFilter.value = '';
            albumFilter.value = '';
            yearFilter.value = '';
            popularityFilter.value = 0;
            popularityValue.textContent = '0';
            searchInput.value = '';
            applyFilters();
        });

        // Search function
        searchButton.addEventListener('click', () => {
            applyFilters();
        });

        searchInput.addEventListener('keyup', (e) => {
            if (e.key === 'Enter') {
                applyFilters();
            }
        });

        // Apply filters when select elements change
        artistFilter.addEventListener('change', applyFilters);
        albumFilter.addEventListener('change', applyFilters);
        yearFilter.addEventListener('change', applyFilters);

        function applyFilters() {
            const searchText = searchInput.value.toLowerCase();
            const artist = artistFilter.value;
            const album = albumFilter.value;
            const minPopularity = parseInt(popularityFilter.value);
            const year = yearFilter.value;

            // Filter the allRows array to get filteredRows
            filteredRows = allRows.filter(row => {
                const rowArtist = row.getAttribute('data-artist');
                const rowAlbum = row.getAttribute('data-album');
                const rowPopularity = parseInt(row.getAttribute('data-popularity')) || 0;
                const rowReleaseDate = row.getAttribute('data-release-date');
                const rowYear = rowReleaseDate ? rowReleaseDate.split('-')[0] : '';

                const trackName = row.cells[1].textContent.toLowerCase();
                const artistName = row.cells[2].textContent.toLowerCase();
                const albumName = row.cells[3].textContent.toLowerCase();

                const matchesSearch = !searchText ||
                    trackName.includes(searchText) ||
                    artistName.includes(searchText) ||
                    albumName.includes(searchText);

                const matchesArtist = !artist || rowArtist === artist;
                const matchesAlbum = !album || rowAlbum === album;
                const matchesPopularity = rowPopularity >= minPopularity;
                const matchesYear = !year || rowYear === year;

                return matchesSearch && matchesArtist && matchesAlbum && matchesPopularity && matchesYear;
            });

            // Reset to first page when filters change
            currentPage = 1;

            // Render the table with the filtered rows
            renderTable();
        }

        // Make sure we call collectRows() to initialize pagination
        collectRows();
    }

    // Start the preloading process
    processDataInChunks();
});
