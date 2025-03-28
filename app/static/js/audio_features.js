// Script to handle audio features visualization functionality
document.addEventListener('DOMContentLoaded', function() {
    // Store chart instances to properly manage them
    window.charts = {
        radar: null,
        energyValence: null,
        danceTempo: null
    };

    // Add CSS for collapsible sections
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
        .chart-toggle i {
            transition: transform 0.2s;
        }
        .chart-toggle[aria-expanded="false"] i {
            transform: rotate(180deg);
        }
    `;
    document.head.appendChild(style);

    // Global variable to store all rows from the table (not just current page)
    let allTrackRows = [];

    // Set charts to be collapsed by default
    const chartContainers = [
        'radarChartContainer',
        'energyValenceChartContainer',
        'danceabilityTempoChartContainer'
    ];

    // Force collapse all chart containers immediately on page load
    chartContainers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (container) {
            container.classList.remove('show');
            const button = document.querySelector(`[data-bs-target="#${containerId}"]`);
            if (button) {
                button.setAttribute('aria-expanded', 'false');
                const icon = button.querySelector('i');
                if (icon) icon.classList.replace('bi-chevron-up', 'bi-chevron-down');
            }
            // Save the collapsed state
            localStorage.setItem(`spiffy-collapse-${containerId}`, 'collapsed');
        }
    });

    // Track chart collapse state in localStorage
    const collapseButtons = document.querySelectorAll('[data-bs-toggle="collapse"]');
    collapseButtons.forEach(button => {
        if (button.getAttribute('data-bs-target')) {
            const targetId = button.getAttribute('data-bs-target').substring(1);
            const storageKey = `spiffy-collapse-${targetId}`;

            // Save collapse state and update icon
            button.addEventListener('click', function() {
                const isExpanded = button.getAttribute('aria-expanded') === 'true';
                localStorage.setItem(storageKey, isExpanded ? 'collapsed' : 'expanded');

                // Update the icon
                const icon = button.querySelector('i');
                if (icon) {
                    if (isExpanded) {
                        icon.classList.replace('bi-chevron-up', 'bi-chevron-down');
                    } else {
                        icon.classList.replace('bi-chevron-down', 'bi-chevron-up');
                    }
                }

                // Initialize charts when expanded
                if (!isExpanded && chartContainers.includes(targetId)) {
                    setTimeout(() => initializeCharts(collectAllTrackData()), 50);
                }
            });
        }
    });

    // Initialize table functionality
    initializeTableFunctionality();

    // Function to capture ALL rows from the table before pagination
    function captureAllTableRows() {
        const table = document.getElementById('tracksTable');
        if (!table) return [];

        const rows = table.querySelectorAll('tbody tr.track-row');
        return Array.from(rows);
    }

    // Function to collect audio feature data from ALL track rows (before pagination)
    function collectAllTrackData() {
        if (allTrackRows.length === 0) return [];

        // Extract data from all track rows
        const tracks = [];
        allTrackRows.forEach(row => {
            const track = {
                name: row.getAttribute('data-track') || '',
                artists: row.getAttribute('data-artist') || '',
                album: row.getAttribute('data-album') || '',
                danceability: parseFloat(row.getAttribute('data-danceability')) || 0,
                energy: parseFloat(row.getAttribute('data-energy')) || 0,
                valence: parseFloat(row.getAttribute('data-valence')) || 0,
                tempo: parseFloat(row.getAttribute('data-tempo')) || 0,
                key: row.getAttribute('data-key') || '',
                data_source: row.getAttribute('data-source') || 'unknown',
                acousticness: parseFloat(row.getAttribute('data-acousticness')) || 0,
                instrumentalness: parseFloat(row.getAttribute('data-instrumentalness')) || 0,
                liveness: parseFloat(row.getAttribute('data-liveness')) || 0,
                speechiness: parseFloat(row.getAttribute('data-speechiness')) || 0
            };
            tracks.push(track);
        });

        return tracks;
    }

    // Function to initialize the charts with the given track data
    function initializeCharts(tracks) {
        console.log(`Creating charts with ${tracks.length} total tracks`);

        if (!tracks || tracks.length === 0) return;

        // Count data sources
        const sources = {};
        tracks.forEach(track => {
            const source = track.data_source || 'unknown';
            sources[source] = (sources[source] || 0) + 1;
        });

        // Calculate average values for radar chart
        const features = [
            'danceability', 'energy', 'valence',
            'acousticness', 'instrumentalness', 'liveness', 'speechiness'
        ];

        const averages = {};
        features.forEach(feature => {
            const validTracks = tracks.filter(t => t[feature] !== undefined && !isNaN(t[feature]));
            if (validTracks.length > 0) {
                const sum = validTracks.reduce((total, track) => total + (parseFloat(track[feature]) || 0), 0);
                averages[feature] = sum / validTracks.length;
            } else {
                averages[feature] = 0;
            }
        });

        // Create radar chart with valid data
        const validFeatures = features.filter(f => averages[f] !== undefined);
        if (validFeatures.length > 0) {
            const ctxRadar = document.getElementById('featuresRadarChart');
            if (ctxRadar && ctxRadar.getContext) {
                // Clean up existing chart if it exists
                if (window.charts.radar instanceof Chart) {
                    window.charts.radar.destroy();
                    window.charts.radar = null;
                }

                window.charts.radar = new Chart(ctxRadar.getContext('2d'), {
                    type: 'radar',
                    data: {
                        labels: validFeatures.map(f => f.charAt(0).toUpperCase() + f.slice(1)),
                        datasets: [{
                            label: 'Your Music Profile',
                            data: validFeatures.map(f => averages[f]),
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 2,
                            pointBackgroundColor: 'rgba(75, 192, 192, 1)'
                        }]
                    },
                    options: {
                        scales: {
                            r: {
                                min: 0,
                                max: 1,
                                ticks: {
                                    stepSize: 0.2
                                }
                            }
                        }
                    }
                });
            }
        }

        // Create scatter plot for energy vs valence
        const energyValenceData = tracks
            .filter(t => typeof t.energy === 'number' && !isNaN(t.energy) &&
                        typeof t.valence === 'number' && !isNaN(t.valence))
            .map(t => ({
                x: t.energy,
                y: t.valence,
                name: t.name,
                artists: t.artists
            }));

        if (energyValenceData.length > 0) {
            const ctxScatter1 = document.getElementById('energyValenceChart');
            if (ctxScatter1 && ctxScatter1.getContext) {
                // Clean up existing chart if it exists
                if (window.charts.energyValence instanceof Chart) {
                    window.charts.energyValence.destroy();
                    window.charts.energyValence = null;
                }

                window.charts.energyValence = new Chart(ctxScatter1.getContext('2d'), {
                    type: 'scatter',
                    data: {
                        datasets: [{
                            label: 'Tracks',
                            data: energyValenceData,
                            backgroundColor: 'rgba(54, 162, 235, 0.5)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: 'Energy'
                                },
                                min: 0,
                                max: 1
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Valence (Positiveness)'
                                },
                                min: 0,
                                max: 1
                            }
                        },
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const point = context.raw;
                                        return `${point.name} by ${point.artists} (E: ${point.x.toFixed(2)}, V: ${point.y.toFixed(2)})`;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }

        // Create scatter plot for danceability vs tempo
        const danceTempoData = tracks
            .filter(t => typeof t.danceability === 'number' && !isNaN(t.danceability) &&
                        typeof t.tempo === 'number' && !isNaN(t.tempo))
            .map(t => ({
                x: t.danceability,
                y: t.tempo,
                name: t.name,
                artists: t.artists
            }));

        if (danceTempoData.length > 0) {
            const ctxScatter2 = document.getElementById('danceabilityTempoChart');
            if (ctxScatter2 && ctxScatter2.getContext) {
                // Clean up existing chart if it exists
                if (window.charts.danceTempo instanceof Chart) {
                    window.charts.danceTempo.destroy();
                    window.charts.danceTempo = null;
                }

                window.charts.danceTempo = new Chart(ctxScatter2.getContext('2d'), {
                    type: 'scatter',
                    data: {
                        datasets: [{
                            label: 'Tracks',
                            data: danceTempoData,
                            backgroundColor: 'rgba(255, 99, 132, 0.5)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1,
                            pointRadius: 4,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: 'Danceability'
                                },
                                min: 0,
                                max: 1
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Tempo (BPM)'
                                },
                                min: Math.max(60, Math.min(...danceTempoData.map(d => d.y)) - 20),
                                max: Math.min(200, Math.max(...danceTempoData.map(d => d.y)) + 20)
                            }
                        },
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const point = context.raw;
                                        return `${point.name} by ${point.artists} (D: ${point.x.toFixed(2)}, T: ${Math.round(point.y)} BPM)`;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }
    }

    // Function to handle the table functionality including pagination and filtering
    function initializeTableFunctionality() {
        // Pagination variables
        let currentPage = 1;
        let pageSize = 50; // Default
        let allRows = [];
        let filteredRows = [];

        // Table Sorting
        let currentSort = { column: null, direction: 'asc' };

        // Store original details rows for reference
        const detailsContent = {};

        // Prepare data for filters
        const artistSet = new Set();
        const albumSet = new Set();

        // Initialize pagination
        const pageSizeSelect = document.getElementById('pageSizeSelect');
        pageSizeSelect.addEventListener('change', function() {
            pageSize = parseInt(this.value);
            currentPage = 1; // Reset to first page
            renderTable();
        });

        // Capture ALL rows before pagination and preserve details
        function collectRows() {
            const table = document.getElementById('tracksTable');
            const tbody = table.querySelector('tbody');

            // First, capture ALL rows from the table (before pagination)
            allTrackRows = captureAllTableRows();

            // Then get all regular rows (not detail rows)
            allRows = Array.from(tbody.querySelectorAll('tr:not(.collapse)'));

            // Store original index for each row
            allRows.forEach((row, index) => {
                const detailsId = row.querySelector('button[data-bs-target]')?.getAttribute('data-bs-target');
                if (detailsId) {
                    const originalIndex = detailsId.replace('#details-', '');
                    row.setAttribute('data-original-index', originalIndex);

                    // Find the details row for this track
                    const detailsRow = document.querySelector(detailsId);
                    if (detailsRow) {
                        // Store the inner content of the details row
                        detailsContent[originalIndex] = detailsRow.querySelector('td').innerHTML;
                    }
                }
            });

            // Process track data for filters
            allTrackRows.forEach(row => {
                const artist = row.getAttribute('data-artist');
                const album = row.getAttribute('data-album');

                if (artist) artistSet.add(artist);
                if (album) albumSet.add(album);
            });

            // Initialize filtered rows
            filteredRows = [...allRows];

            // Populate filters after getting all data
            populateFilters();

            // Initial render
            renderTable();

            // Initialize charts with all track data
            // Use a delay to ensure the containers are ready
            setTimeout(() => {
                const allTrackData = collectAllTrackData();
                if (allTrackData.length > 0) {
                    initializeCharts(allTrackData);
                }
            }, 200);
        }

        // Populate filters
        function populateFilters() {
            const artistFilter = document.getElementById('artistFilter');
            const albumFilter = document.getElementById('albumFilter');
            const danceabilityFilter = document.getElementById('danceabilityFilter');
            const danceabilityValue = document.getElementById('danceabilityValue');
            const energyFilter = document.getElementById('energyFilter');
            const energyValue = document.getElementById('energyValue');

            // Clear existing options first
            artistFilter.innerHTML = '<option value="">All Artists</option>';
            albumFilter.innerHTML = '<option value="">All Albums</option>';

            // Sort artists alphabetically
            const sortedArtists = Array.from(artistSet).sort();

            // Add artists to filter
            sortedArtists.forEach(artist => {
                const option = document.createElement('option');
                option.value = artist;
                option.textContent = artist;
                artistFilter.appendChild(option);
            });

            // Sort albums alphabetically
            const sortedAlbums = Array.from(albumSet).sort();

            // Add albums to filter
            sortedAlbums.forEach(album => {
                const option = document.createElement('option');
                option.value = album;
                option.textContent = album;
                albumFilter.appendChild(option);
            });

            // Update filter sliders value display
            danceabilityFilter.addEventListener('input', function() {
                danceabilityValue.textContent = this.value;
                applyFilters();
            });

            energyFilter.addEventListener('input', function() {
                energyValue.textContent = this.value;
                applyFilters();
            });

            // Initialize filter displays
            danceabilityValue.textContent = danceabilityFilter.value;
            energyValue.textContent = energyFilter.value;

            // Apply filters when select elements change
            artistFilter.addEventListener('change', applyFilters);
            albumFilter.addEventListener('change', applyFilters);

            // Search and reset buttons
            const searchInput = document.getElementById('searchInput');
            const searchButton = document.getElementById('searchButton');
            const resetFilters = document.getElementById('resetFilters');

            // Search function
            searchButton.addEventListener('click', () => {
                applyFilters();
            });

            searchInput.addEventListener('keyup', (e) => {
                if (e.key === 'Enter') {
                    applyFilters();
                }
            });

            // Reset filters
            resetFilters.addEventListener('click', () => {
                artistFilter.value = '';
                albumFilter.value = '';
                danceabilityFilter.value = 0;
                danceabilityValue.textContent = '0';
                energyFilter.value = 0;
                energyValue.textContent = '0';
                searchInput.value = '';
                applyFilters();
            });

            // Toggle filters container
            const toggleFilters = document.getElementById('toggleFilters');
            const filtersContainer = document.getElementById('filtersContainer');

            toggleFilters.addEventListener('click', () => {
                const filtersCollapse = new bootstrap.Collapse(filtersContainer);
                filtersCollapse.toggle();
            });
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
                    const newDetailsRow = document.createElement('tr');
                    newDetailsRow.className = 'collapse';
                    newDetailsRow.id = newDetailsID;

                    // Create a cell that spans the entire row
                    const detailsCell = document.createElement('td');
                    detailsCell.setAttribute('colspan', '10');
                    detailsCell.innerHTML = detailsContent[originalIndex];

                    // Process JSON toggle buttons in the details cell
                    const jsonToggle = detailsCell.querySelector('.json-toggle');
                    if (jsonToggle) {
                        const jsonCollapseTarget = jsonToggle.getAttribute('data-bs-target');
                        if (jsonCollapseTarget) {
                            const newJsonTargetId = `json-${newDetailsID}`;
                            jsonToggle.setAttribute('data-bs-target', `#${newJsonTargetId}`);

                            const jsonContainer = detailsCell.querySelector(jsonCollapseTarget);
                            if (jsonContainer) {
                                jsonContainer.id = newJsonTargetId;
                            }
                        }
                    }

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

        function applyFilters() {
            const searchInput = document.getElementById('searchInput');
            const artistFilter = document.getElementById('artistFilter');
            const albumFilter = document.getElementById('albumFilter');
            const danceabilityFilter = document.getElementById('danceabilityFilter');
            const energyFilter = document.getElementById('energyFilter');

            const searchText = searchInput.value.toLowerCase();
            const artist = artistFilter.value;
            const album = albumFilter.value;
            const minDanceability = parseInt(danceabilityFilter.value) / 100;  // Convert to 0-1 scale
            const minEnergy = parseInt(energyFilter.value) / 100;  // Convert to 0-1 scale

            // Filter the allRows array to get filteredRows
            filteredRows = allRows.filter(row => {
                const rowArtist = row.getAttribute('data-artist');
                const rowAlbum = row.getAttribute('data-album');
                const rowDanceability = parseFloat(row.getAttribute('data-danceability')) || 0;
                const rowEnergy = parseFloat(row.getAttribute('data-energy')) || 0;

                const trackName = row.cells[0].textContent.toLowerCase();
                const artistName = row.cells[1].textContent.toLowerCase();
                const albumName = row.cells[2].textContent.toLowerCase();

                const matchesSearch = !searchText ||
                    trackName.includes(searchText) ||
                    artistName.includes(searchText) ||
                    albumName.includes(searchText);

                const matchesArtist = !artist || rowArtist === artist;
                const matchesAlbum = !album || rowAlbum === album;
                const matchesDanceability = rowDanceability >= minDanceability;
                const matchesEnergy = rowEnergy >= minEnergy;

                return matchesSearch && matchesArtist && matchesAlbum && matchesDanceability && matchesEnergy;
            });

            // Reset to first page when filters change
            currentPage = 1;

            // Render the table with the filtered rows
            renderTable();

            // Now filter the allTrackRows the same way to update the charts
            const filteredTrackRows = allTrackRows.filter(row => {
                const rowArtist = row.getAttribute('data-artist');
                const rowAlbum = row.getAttribute('data-album');
                const rowDanceability = parseFloat(row.getAttribute('data-danceability')) || 0;
                const rowEnergy = parseFloat(row.getAttribute('data-energy')) || 0;

                const trackName = row.cells[0].textContent.toLowerCase();
                const artistName = row.cells[1].textContent.toLowerCase();
                const albumName = row.cells[2].textContent.toLowerCase();

                const matchesSearch = !searchText ||
                    trackName.includes(searchText) ||
                    artistName.includes(searchText) ||
                    albumName.includes(searchText);

                const matchesArtist = !artist || rowArtist === artist;
                const matchesAlbum = !album || rowAlbum === album;
                const matchesDanceability = rowDanceability >= minDanceability;
                const matchesEnergy = rowEnergy >= minEnergy;

                return matchesSearch && matchesArtist && matchesAlbum && matchesDanceability && matchesEnergy;
            });

            // Extract data from filtered rows
            const filteredTrackData = [];
            filteredTrackRows.forEach(row => {
                const track = {
                    name: row.getAttribute('data-track') || '',
                    artists: row.getAttribute('data-artist') || '',
                    album: row.getAttribute('data-album') || '',
                    danceability: parseFloat(row.getAttribute('data-danceability')) || 0,
                    energy: parseFloat(row.getAttribute('data-energy')) || 0,
                    valence: parseFloat(row.getAttribute('data-valence')) || 0,
                    tempo: parseFloat(row.getAttribute('data-tempo')) || 0,
                    key: row.getAttribute('data-key') || '',
                    data_source: row.getAttribute('data-source') || 'unknown',
                    acousticness: parseFloat(row.getAttribute('data-acousticness')) || 0,
                    instrumentalness: parseFloat(row.getAttribute('data-instrumentalness')) || 0,
                    liveness: parseFloat(row.getAttribute('data-liveness')) || 0,
                    speechiness: parseFloat(row.getAttribute('data-speechiness')) || 0
                };
                filteredTrackData.push(track);
            });

            // Update the charts with filtered data
            console.log(`Updating charts with ${filteredTrackData.length} filtered tracks`);
            initializeCharts(filteredTrackData);
        }

        // Table sorting
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
                    case 'track':
                        aValue = a.getAttribute('data-track')?.toLowerCase() || '';
                        bValue = b.getAttribute('data-track')?.toLowerCase() || '';
                        break;
                    case 'artist':
                        aValue = a.getAttribute('data-artist')?.toLowerCase() || '';
                        bValue = b.getAttribute('data-artist')?.toLowerCase() || '';
                        break;
                    case 'album':
                        aValue = a.getAttribute('data-album')?.toLowerCase() || '';
                        bValue = b.getAttribute('data-album')?.toLowerCase() || '';
                        break;
                    case 'danceability':
                        aValue = parseFloat(a.getAttribute('data-danceability')) || 0;
                        bValue = parseFloat(b.getAttribute('data-danceability')) || 0;
                        break;
                    case 'energy':
                        aValue = parseFloat(a.getAttribute('data-energy')) || 0;
                        bValue = parseFloat(b.getAttribute('data-energy')) || 0;
                        break;
                    case 'valence':
                        aValue = parseFloat(a.getAttribute('data-valence')) || 0;
                        bValue = parseFloat(b.getAttribute('data-valence')) || 0;
                        break;
                    case 'tempo':
                        aValue = parseFloat(a.getAttribute('data-tempo')) || 0;
                        bValue = parseFloat(b.getAttribute('data-tempo')) || 0;
                        break;
                    case 'key':
                        aValue = a.getAttribute('data-key') || '';
                        bValue = b.getAttribute('data-key') || '';
                        break;
                    case 'source':
                        aValue = a.getAttribute('data-source') || '';
                        bValue = b.getAttribute('data-source') || '';
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

        // Initialize the table functionality
        collectRows();
    }
});
