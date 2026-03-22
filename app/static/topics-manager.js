/**
 * TopicsManager
 * Handles client-side search, filtering, and pagination for the Saved Topics list.
 */
class TopicsManager {
    constructor(options = {}) {
        this.listId = options.listId || 'topics-list';
        this.inputId = options.inputId || 'topic-search';
        this.paginationId = options.paginationId || 'topics-pagination';
        this.pageSizeId = options.pageSizeId || 'topics-page-size';
        this.countId = options.countId || 'topics-count';

        this.items = []; // Array of DOM elements (li)
        this.filteredIndexes = []; // Array of indexes dealing with filtered items
        this.currentPage = 1;
        this.pageSize = 5; // Default page size
        this.toastElement = null;
        this.toastTimeout = null;

        this.init();
    }

    init() {
        // Cache DOM elements
        this.listContainer = document.querySelector(`.${this.listId} ul`);
        if (!this.listContainer) return;

        this.inputElement = document.getElementById(this.inputId);
        this.paginationContainer = document.getElementById(this.paginationId);
        this.pageSizeSelect = document.getElementById(this.pageSizeId);
        this.countElement = document.getElementById(this.countId);

        // Initialize items
        const rawItems = Array.from(this.listContainer.children);
        this.items = rawItems.map((el, index) => ({
            element: el,
            index: index,
            name: el.querySelector('.topic-name').textContent.toLowerCase().trim()
        }));

        if (this.pageSizeSelect) {
            this.pageSize = this.pageSizeSelect.value === 'all'
                ? this.items.length
                : parseInt(this.pageSizeSelect.value, 10);
        }

        // Initial Filter (shows all)
        this.filter('');

        // Bind Events
        if (this.inputElement) {
            this.inputElement.addEventListener('input', (e) => {
                this.currentPage = 1;
                this.filter(e.target.value);
            });
        }

        if (this.pageSizeSelect) {
            this.pageSizeSelect.addEventListener('change', (e) => {
                this.pageSize = e.target.value === 'all' ? this.items.length : parseInt(e.target.value);
                this.currentPage = 1;
                this.render();
            });
        }

        // Topic Click Interaction
        this.listContainer.addEventListener('click', (e) => {
            // Ignore if clicking a button or link
            if (e.target.closest('a, button')) return;

            this.showToast('Select a mode to continue');
        });
    }

    filter(query) {
        query = query.toLowerCase().trim();

        if (!query) {
            this.filteredIndexes = this.items.map(item => item.index);
        } else {
            this.filteredIndexes = this.items
                .filter(item => item.name.includes(query))
                .map(item => item.index);
        }

        this.render();
    }

    render() {
        // Calculate pagination bounds
        const totalItems = this.filteredIndexes.length;
        const totalPages = Math.ceil(totalItems / this.pageSize);

        // Ensure current page is valid
        if (this.currentPage > totalPages) this.currentPage = totalPages || 1;
        if (this.currentPage < 1) this.currentPage = 1;

        const startIndex = (this.currentPage - 1) * this.pageSize;
        const endIndex = startIndex + this.pageSize;

        // Determine which indexes are visible on this page
        const visibleIndexes = new Set(
            this.filteredIndexes.slice(startIndex, endIndex)
        );

        // Update DOM visibility
        this.items.forEach(item => {
            if (visibleIndexes.has(item.index)) {
                item.element.style.display = 'flex'; // Restore layout
                // Add a small animation/transition class if desired
                item.element.classList.add('visible');
            } else {
                item.element.style.display = 'none';
                item.element.classList.remove('visible');
            }
        });

        // Update UI
        this.updatePaginationUI(totalPages);
        this.updateCountUI(startIndex + 1, Math.min(endIndex, totalItems), totalItems);
        this.toggleEmptyState(totalItems === 0);
    }

    updatePaginationUI(totalPages) {
        if (!this.paginationContainer) return;

        this.paginationContainer.innerHTML = '';

        if (totalPages <= 1) return; // Hide pagination if only 1 page

        // Previous Button
        const prevBtn = this.createPageBtn('Prev', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.render();
            }
        });
        prevBtn.disabled = this.currentPage === 1;
        this.paginationContainer.appendChild(prevBtn);

        // Page Numbers (Simple version: generic 1, 2... N logic)
        // For very large content, we might want ellipsis, but let's keep it simple first
        let minPage = Math.max(1, this.currentPage - 2);
        let maxPage = Math.min(totalPages, minPage + 4);

        if (maxPage - minPage < 4) {
            minPage = Math.max(1, maxPage - 4);
        }

        for (let i = minPage; i <= maxPage; i++) {
            const pageBtn = this.createPageBtn(i, () => {
                this.currentPage = i;
                this.render();
            });
            if (i === this.currentPage) pageBtn.classList.add('active');
            this.paginationContainer.appendChild(pageBtn);
        }

        // Next Button
        const nextBtn = this.createPageBtn('Next', () => {
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.render();
            }
        });
        nextBtn.disabled = this.currentPage === totalPages;
        this.paginationContainer.appendChild(nextBtn);
    }

    createPageBtn(label, onClick) {
        const btn = document.createElement('button');
        btn.textContent = label;
        btn.className = 'pagination-btn';
        btn.addEventListener('click', onClick);
        return btn;
    }

    updateCountUI(start, end, total) {
        if (!this.countElement) return;
        if (total === 0) {
            this.countElement.textContent = 'No topics found';
        } else {
            this.countElement.textContent = `Showing ${start}-${end} of ${total}`;
        }
    }

    toggleEmptyState(isEmpty) {
        let emptyMsg = this.listContainer.parentNode.querySelector('.no-results-message');

        if (isEmpty) {
            if (!emptyMsg) {
                emptyMsg = document.createElement('div');
                emptyMsg.className = 'no-results-message';
                emptyMsg.textContent = 'No matching topics found.';
                emptyMsg.style.textAlign = 'center';
                emptyMsg.style.padding = '20px';
                emptyMsg.style.color = 'var(--text-muted)';
                this.listContainer.parentNode.appendChild(emptyMsg);
            }
            emptyMsg.style.display = 'block';
        } else if (emptyMsg) {
            emptyMsg.style.display = 'none';
        }
    }

    showToast(message) {
        if (!this.toastElement) {
            this.toastElement = document.createElement('div');
            this.toastElement.className = 'topics-toast';
            document.body.appendChild(this.toastElement);
        }

        this.toastElement.textContent = message;
        // Trigger reflow/repaint to ensure transition plays if strictly needed,
        // but adding class usually works fine.
        requestAnimationFrame(() => {
            this.toastElement.classList.add('show');
        });

        if (this.toastTimeout) clearTimeout(this.toastTimeout);

        this.toastTimeout = setTimeout(() => {
            this.toastElement.classList.remove('show');
        }, 3000);
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    window.topicsManager = new TopicsManager();
});
