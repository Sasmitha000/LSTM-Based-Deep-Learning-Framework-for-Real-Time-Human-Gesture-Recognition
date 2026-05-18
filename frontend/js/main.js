document.addEventListener('DOMContentLoaded', function() {
    const currentPage = window.location.pathname.split('/').pop();
    const navLinks = document.querySelectorAll('nav ul li a');
    navLinks.forEach(link => {
        const linkPage = link.getAttribute('href');
        if (linkPage === currentPage || (currentPage === '' && linkPage === 'index.html')) {
            link.classList.add('active');
        }
    });
});

// ========================================
// MOBILE MENU TOGGLE
// ========================================

function toggleMobileMenu() {
    const nav = document.querySelector('nav');
    const hamburger = document.querySelector('.hamburger');
    const overlay = document.querySelector('.nav-overlay');
    
    nav.classList.toggle('active');
    hamburger.classList.toggle('active');
    overlay.classList.toggle('active');
    
    // Prevent body scroll when menu is open
    if (nav.classList.contains('active')) {
        document.body.style.overflow = 'hidden';
    } else {
        document.body.style.overflow = '';
    }
}

// Close menu when clicking on a nav link
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('nav a');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            const nav = document.querySelector('nav');
            const hamburger = document.querySelector('.hamburger');
            const overlay = document.querySelector('.nav-overlay');
            
            if (nav.classList.contains('active')) {
                nav.classList.remove('active');
                hamburger.classList.remove('active');
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });
});

// ========================================
// MOBILE MENU TOGGLE (UPDATED)
// ========================================

function toggleMobileMenu() {
    const nav = document.querySelector('nav');
    const hamburger = document.querySelector('.hamburger');
    
    nav.classList.toggle('active');
    hamburger.classList.toggle('active');
    
    // Prevent body scroll when menu is open
    if (nav.classList.contains('active')) {
        document.body.style.overflow = 'hidden';
    } else {
        document.body.style.overflow = '';
    }
}

// Close menu when clicking on a nav link
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('nav a');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            const nav = document.querySelector('nav');
            const hamburger = document.querySelector('.hamburger');
            
            if (nav && nav.classList.contains('active')) {
                nav.classList.remove('active');
                if (hamburger) hamburger.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });
    
    // Close menu on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const nav = document.querySelector('nav');
            const hamburger = document.querySelector('.hamburger');
            
            if (nav && nav.classList.contains('active')) {
                nav.classList.remove('active');
                if (hamburger) hamburger.classList.remove('active');
                document.body.style.overflow = '';
            }
        }
    });
});
