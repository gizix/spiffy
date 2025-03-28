// Script to handle the artists visualization page
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

    // Immediately show the main content
    document.getElementById('initialLoadingContainer').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';

    // Initialize main functionality
    function initializeMainFunctionality() {
        console.log('Initializing main functionality');

        // Get all artist rows
        const artistRows = document.querySelectorAll('.artist-row');
        console.log('Found', artistRows.length, 'artist rows');

        if (artistRows.length === 0) {
            console.log('No artist rows found!');
            document.getElementById('displayedRowsInfo').textContent = "No artists found. Please sync your artist data first.";
            return;
        }

        // Prepare data for filters
        const artists = [];
        const genreSet = new Set();
        let maxFollowers = 0;

        // Pagination variables
        let currentPage = 1;
        let pageSize = 50; // Default
        let allRows = Array.from(artistRows); // Store all rows immediately
        let filteredRows = [...allRows];      // Initialize filtered rows

        // Store original details rows for reference
        const detailsContent = {};

        // Table Sorting
        let currentSort = { column: 'name', direction: 'asc' };

        // Process artists data for filters
        artistRows.forEach(row => {
            const artist = {
                name: row.getAttribute('data-name'),
                genres: row.getAttribute('data-genres').split(',').filter(genre => genre.trim() !== ''),
                popularity: parseInt(row.getAttribute('data-popularity')) || 0,
                followers: parseInt(row.getAttribute('data-followers')) || 0
            };

            artists.push(artist);

            // Collect unique genres for filter
            artist.genres.forEach(genre => {
                if (genre.trim()) {
                    genreSet.add(genre.trim());
                }
            });

            // Track max followers for the range input
            maxFollowers = Math.max(maxFollowers, artist.followers);

            // Store original index
            const originalIndex = row.cells[0].textContent;
            row.setAttribute('data-original-index', originalIndex);

            // Find and store details content
            const detailsRow = document.getElementById(`details-${originalIndex}`);
            if (detailsRow) {
                detailsContent[originalIndex] = detailsRow.querySelector('td').innerHTML;
            }
        });

        console.log('Processed', artists.length, 'artists with', genreSet.size, 'unique genres');
        console.log('Max followers:', maxFollowers);

        // Initialize pagination
        const pageSizeSelect = document.getElementById('pageSizeSelect');
        pageSizeSelect.addEventListener('change', function() {
            pageSize = parseInt(this.value);
            currentPage = 1; // Reset to first page
            renderTable();
        });

        // Populate genre filter
        const genreFilter = document.getElementById('genreFilter');
        const popularityFilter = document.getElementById('popularityFilter');
        const popularityValue = document.getElementById('popularityValue');
        const followersFilter = document.getElementById('followersFilter');
        const followersValue = document.getElementById('followersValue');

        // Set the max value for followers filter
        followersFilter.max = 100; // We'll use percentages for the slider
        followersValue.textContent = '0';

        // Map followers slider to actual count
        function getFollowersFromSlider(sliderValue) {
            // Convert slider percentage to actual followers count
            return Math.floor((sliderValue / 100) * maxFollowers);
        }

        function formatFollowersCount(count) {
            if (count >= 1000000) {
                return (count / 1000000).toFixed(1) + 'M';
            } else if (count >= 1000) {
                return (count / 1000).toFixed(1) + 'K';
            }
            return count.toString();
        }

        // Sort genres alphabetically for the filter
        const sortedGenres = Array.from(genreSet).sort();

        // Add genres to filter
        sortedGenres.forEach(genre => {
            const option = document.createElement('option');
            option.value = genre;
            option.textContent = genre;
            genreFilter.appendChild(option);
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
                    case 'name':
                        aValue = a.cells[1].textContent.toLowerCase();
                        bValue = b.cells[1].textContent.toLowerCase();
                        break;
                    case 'genres':
                        aValue = a.cells[2].textContent.toLowerCase();
                        bValue = b.cells[2].textContent.toLowerCase();
                        break;
                    case 'popularity':
                        aValue = parseInt(a.getAttribute('data-popularity')) || 0;
                        bValue = parseInt(b.getAttribute('data-popularity')) || 0;
                        break;
                    case 'followers':
                        aValue = parseInt(a.getAttribute('data-followers')) || 0;
                        bValue = parseInt(b.getAttribute('data-followers')) || 0;
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
            console.log('Rendering table with', filteredRows.length, 'filtered rows');
            const table = document.getElementById('artistsTable');
            const tbody = table.querySelector('tbody');

            // Clear tbody
            console.log('Clearing tbody...');
            while (tbody.firstChild) {
                tbody.removeChild(tbody.firstChild);
            }
            console.log('Tbody cleared');

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
                `Showing ${displayedRows.length} of ${filteredRows.length} artists`;

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
                    // Process the HTML to make the JSON section collapsible
                    const detailsHTML = detailsContent[originalIndex];
                    const processedHTML = detailsHTML.replace(
                        /<h6>.*?Full Data.*?<\/h6>\s*<div class="collapse json-container".*?>/s,
                        `<h6>
                            <button class="btn btn-sm btn-outline-secondary json-toggle" type="button" 
                                data-bs-toggle="collapse" 
                                data-bs-target="#json-${newDetailsID}" 
                                aria-expanded="false">
                                Full Data <i class="bi bi-chevron-down"></i>
                            </button>
                        </h6>
                        <div class="collapse json-container" id="json-${newDetailsID}">`
                    );

                    const newDetailsRow = document.createElement('tr');
                    newDetailsRow.className = 'collapse';
                    newDetailsRow.id = newDetailsID;

                    // Create a cell that spans the entire row
                    const detailsCell = document.createElement('td');
                    detailsCell.setAttribute('colspan', '6');
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

            // Page numbers - show limited page links with ellipsis
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

        // Update filter value displays
        popularityFilter.addEventListener('input', () => {
            popularityValue.textContent = popularityFilter.value;
            applyFilters();
        });

        followersFilter.addEventListener('input', () => {
            const actualFollowers = getFollowersFromSlider(followersFilter.value);
            followersValue.textContent = formatFollowersCount(actualFollowers);
            applyFilters();
        });

        // Reset filters
        resetFilters.addEventListener('click', () => {
            genreFilter.value = '';
            popularityFilter.value = 0;
            popularityValue.textContent = '0';
            followersFilter.value = 0;
            followersValue.textContent = '0';
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
        genreFilter.addEventListener('change', applyFilters);

        function applyFilters() {
            const searchText = searchInput.value.toLowerCase();
            const genre = genreFilter.value;
            const minPopularity = parseInt(popularityFilter.value);
            const minFollowersPercent = parseInt(followersFilter.value);
            const minFollowers = getFollowersFromSlider(minFollowersPercent);

            // Filter the allRows array to get filteredRows
            filteredRows = allRows.filter(row => {
                const rowGenres = row.getAttribute('data-genres').split(',');
                const rowPopularity = parseInt(row.getAttribute('data-popularity')) || 0;
                const rowFollowers = parseInt(row.getAttribute('data-followers')) || 0;

                const artistName = row.cells[1].textContent.toLowerCase();
                const genresText = row.cells[2].textContent.toLowerCase();

                const matchesSearch = !searchText ||
                    artistName.includes(searchText) ||
                    genresText.includes(searchText);

                const matchesGenre = !genre || rowGenres.includes(genre);
                const matchesPopularity = rowPopularity >= minPopularity;
                const matchesFollowers = rowFollowers >= minFollowers;

                return matchesSearch && matchesGenre && matchesPopularity && matchesFollowers;
            });

            // Reset to first page when filters change
            currentPage = 1;

            // Render the table with the filtered rows
            renderTable();
        }

        // Initial sort and render
        sortTable('name', 'asc');
    }

    // Initialize the application
    initializeMainFunctionality();
});
