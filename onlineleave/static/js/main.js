/**
 * Online Leave Management System
 * VMR PRADEEP KUMAR INSTITUTION OF ENGINEERING AND TECHNOLOGY
 * Client-Side JavaScript Enhancements
 */

document.addEventListener('DOMContentLoaded', function () {
    // ── 1. Auto-dismiss Flash Alerts ─────────────────────────────
    const flashAlerts = document.querySelectorAll('.flash-alert');
    if (flashAlerts.length > 0) {
        setTimeout(function () {
            flashAlerts.forEach(function (alert) {
                alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-4px)';
                setTimeout(function () {
                    alert.remove();
                }, 500);
            });
        }, 6000);
    }

    // ── 2. Leave Application Form Interactions ────────────────────
    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');
    const durationBanner = document.getElementById('duration-calc-banner');
    const calculatedDaysSpan = document.getElementById('calculated-days');
    const reasonTextarea = document.getElementById('reason');
    const charCountSpan = document.getElementById('char-count');

    // Set today's date as min for start date
    if (startDateInput) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        const todayStr = `${yyyy}-${mm}-${dd}`;

        startDateInput.setAttribute('min', todayStr);

        function updateDateCalculation() {
            const startVal = startDateInput.value;
            const endVal = endDateInput.value;

            if (startVal) {
                // Ensure end date cannot be earlier than start date
                endDateInput.setAttribute('min', startVal);
                if (endVal && endVal < startVal) {
                    endDateInput.value = startVal;
                }
            }

            if (startVal && endDateInput.value) {
                const sDate = new Date(startVal + 'T00:00:00');
                const eDate = new Date(endDateInput.value + 'T00:00:00');

                if (eDate >= sDate) {
                    const diffTime = eDate - sDate;
                    const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24)) + 1; // inclusive

                    if (calculatedDaysSpan) {
                        calculatedDaysSpan.textContent = diffDays;
                    }
                    if (durationBanner) {
                        durationBanner.style.display = 'flex';
                    }
                } else if (durationBanner) {
                    durationBanner.style.display = 'none';
                }
            } else if (durationBanner) {
                durationBanner.style.display = 'none';
            }
        }

        startDateInput.addEventListener('change', updateDateCalculation);
        if (endDateInput) {
            endDateInput.addEventListener('change', updateDateCalculation);
        }
    }

    // Reason textarea character counter
    if (reasonTextarea && charCountSpan) {
        function updateCharCount() {
            const len = reasonTextarea.value.length;
            charCountSpan.textContent = len;
            if (len >= 500) {
                charCountSpan.style.color = 'var(--status-rejected-text)';
                charCountSpan.style.fontWeight = 'bold';
            } else {
                charCountSpan.style.color = '';
                charCountSpan.style.fontWeight = '';
            }
        }

        reasonTextarea.addEventListener('input', updateCharCount);
        updateCharCount(); // initial state
    }

    // ── 3. Client Validation for Registration Password Match ───────
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', function (e) {
            const pass = document.getElementById('password').value;
            const confirm = document.getElementById('confirm_password').value;

            if (pass.length < 8) {
                alert('Password must be at least 8 characters long.');
                e.preventDefault();
                return false;
            }

            if (pass !== confirm) {
                alert('Passwords do not match. Please verify.');
                e.preventDefault();
                return false;
            }
        });
    }
});
