/*
 * touch_scroll.js
 * Drag-to-scroll for the dashboard.
 *
 * Many 7" Raspberry Pi touchscreens report as a mouse rather than a touch
 * device, so the browser never does native finger-drag scrolling — only the
 * scrollbar works. This adds pointer-based drag scrolling that works whether
 * the panel reports mouse OR touch input, with a small movement threshold so a
 * plain tap on a device row still registers as a click (opens its details).
 */
(function () {
    'use strict';

    function init() {
        var root = document.querySelector('.main-content');
        if (!root || root.dataset.dragScroll === 'on') return;
        root.dataset.dragScroll = 'on';

        var THRESHOLD = 6;          // px before a press becomes a drag
        var target = null;          // the scrollable element being dragged
        var startY = 0;
        var startScroll = 0;
        var dragging = false;
        var moved = false;

        // Walk up from the touched node to the nearest vertically scrollable
        // ancestor (so inner panels scroll too); fall back to .main-content.
        function findScrollable(node) {
            while (node && node !== root.parentElement) {
                if (node.scrollHeight - node.clientHeight > 1) {
                    var oy = getComputedStyle(node).overflowY;
                    if (oy === 'auto' || oy === 'scroll') return node;
                }
                node = node.parentElement;
            }
            return root;
        }

        root.addEventListener('pointerdown', function (e) {
            if (e.pointerType === 'mouse' && e.button !== 0) return; // left button only
            target = findScrollable(e.target);
            startY = e.clientY;
            startScroll = target.scrollTop;
            dragging = true;
            moved = false;
            // Keep receiving move/up events even if the finger leaves the panel.
            try { root.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
        });

        root.addEventListener('pointermove', function (e) {
            if (!dragging || !target) return;
            var dy = e.clientY - startY;
            if (!moved && Math.abs(dy) < THRESHOLD) return;
            if (!moved) {
                moved = true;
                root.classList.add('drag-scrolling'); // disables text selection
            }
            target.scrollTop = startScroll - dy;
            e.preventDefault();
        });

        function endDrag() {
            dragging = false;
            target = null;
            root.classList.remove('drag-scrolling');
        }
        root.addEventListener('pointerup', endDrag);
        root.addEventListener('pointercancel', endDrag);
        root.addEventListener('pointerleave', endDrag);

        // Swallow the click that fires after a real drag, so dragging across a
        // device row doesn't also open its details panel.
        root.addEventListener('click', function (e) {
            if (moved) {
                e.stopPropagation();
                e.preventDefault();
                moved = false;
            }
        }, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
