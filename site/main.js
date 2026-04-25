import './style.css'
import './slides.css'
import gsap from 'gsap'
import { ParticleSystem } from './particles.js'

// --- Canvas Setup ---
const canvas = document.getElementById('bg-canvas')
const system = new ParticleSystem(canvas)

const resize = () => {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    system.resize(window.innerWidth, window.innerHeight)
}
window.addEventListener('resize', resize)
resize()

// --- Slide Management ---
const slides = document.querySelectorAll('.slide')
const container = document.querySelector('.slides-container')
const slideNav = document.getElementById('slide-nav')
let currentSlide = 0

// Create navigation dots
slides.forEach((slide, i) => {
    const dot = document.createElement('div')
    dot.className = 'dot' + (i === 0 ? ' active' : '')
    dot.addEventListener('click', () => goToSlide(i))
    slideNav.appendChild(dot)
})

const dots = document.querySelectorAll('.slide-nav .dot')

// Scene definitions with colors
const sceneMap = {
    'intro': { chaos: 0, shapeInfluence: 0.8, currentShape: 'grid', pressure: 0, failureMode: 0, stability: 0, looping: 0 },
    'chaos': { chaos: 1, shapeInfluence: 0, currentShape: 'cloud', pressure: 0, failureMode: 0, stability: 0, looping: 0 },
    'drift': { chaos: 0.6, shapeInfluence: 0.2, currentShape: 'cloud', pressure: 0, failureMode: 0, stability: 0, looping: 0 },
    'pressure': { chaos: 0.3, shapeInfluence: 0.7, currentShape: 'funnel', pressure: 0.5, failureMode: 0, stability: 0, looping: 0 },
    'funnel': { chaos: 0.8, shapeInfluence: 0.1, currentShape: 'cloud', pressure: 0, failureMode: 0, stability: 0, looping: 0 }, // Start chaotic
    'loop': { chaos: 0.15, shapeInfluence: 0.85, currentShape: 'loop', pressure: 0.2, failureMode: 0, stability: 0, looping: 1 },
    'filter': { chaos: 0.4, shapeInfluence: 0.6, currentShape: 'funnel', pressure: 0.6, failureMode: 0.5, stability: 0, looping: 0 },
    'failure': { chaos: 0.5, shapeInfluence: 0.5, currentShape: 'cloud', pressure: 0.3, failureMode: 1, stability: 0, looping: 0 },
    'stability': { chaos: 0.05, shapeInfluence: 1, currentShape: 'beam', pressure: 0, failureMode: 0, stability: 1, looping: 0 }
}

// Animation cycle for slide 3 (The Solution)
let slide3AnimationInterval = null

function highlightStep(stepNumber) {
    for (let i = 1; i <= 4; i++) {
        const el = document.getElementById(`step-${i}`)
        if (el) {
            el.style.opacity = '0.5'
            el.style.transform = 'scale(1)'
        }
    }
    const currentEl = document.getElementById(`step-${stepNumber}`)
    if (currentEl) {
        currentEl.style.opacity = '1'
        currentEl.style.transform = 'scale(1.05)'
    }
}

function startSlide3Animation() {
    if (slide3AnimationInterval) return
    
    const steps = [
        { chaos: 0.8, shapeInfluence: 0.1, currentShape: 'cloud', pressure: 0, failureMode: 0, color: '#f5a623', step: 0 }, // Chaos — no governance
        { chaos: 0.4, shapeInfluence: 0.5, currentShape: 'funnel', pressure: 0.5, failureMode: 0, color: '#4a90e2', step: 1 }, // Phases
        { chaos: 0.2, shapeInfluence: 0.7, currentShape: 'funnel', pressure: 0.9, failureMode: 0, color: '#7ed321', step: 2 }, // Transactions
        { chaos: 0.15, shapeInfluence: 0.85, currentShape: 'loop', pressure: 0.7, failureMode: 0, looping: 1, color: '#bd10e0', step: 3 }, // Budget gates
        { chaos: 0.05, shapeInfluence: 1, currentShape: 'beam', pressure: 0, failureMode: 0, looping: 0, color: '#7ed321', step: 4 } // Proof traces — order
    ]
    
    let currentStep = 0
    
    // Initialize first step
    const firstStep = steps[0]
    gsap.to(system.state, {
        chaos: firstStep.chaos,
        shapeInfluence: firstStep.shapeInfluence,
        currentShape: firstStep.currentShape,
        pressure: firstStep.pressure,
        failureMode: firstStep.failureMode,
        looping: firstStep.looping || 0,
        duration: 0.8,
        ease: "power2.inOut"
    })
    system.setColor(firstStep.color)
    
    slide3AnimationInterval = setInterval(() => {
        currentStep = (currentStep + 1) % steps.length
        const step = steps[currentStep]
        
        gsap.to(system.state, {
            chaos: step.chaos,
            shapeInfluence: step.shapeInfluence,
            currentShape: step.currentShape,
            pressure: step.pressure,
            failureMode: step.failureMode,
            looping: step.looping || 0,
            duration: 2,
            ease: "power2.inOut"
        })
        system.setColor(step.color)
    }, 3500)
}

function stopSlide3Animation() {
    if (slide3AnimationInterval) {
        clearInterval(slide3AnimationInterval)
        slide3AnimationInterval = null
    }
}

// Navigate to slide
function goToSlide(index) {
    if (index < 0 || index >= slides.length) return
    currentSlide = index

    slides[index].scrollIntoView({ behavior: 'smooth' })

    // Update dots
    dots.forEach((dot, i) => {
        dot.classList.toggle('active', i === index)
    })

    // Update particle state
    const scene = slides[index].dataset.scene
    const color = slides[index].dataset.color

    // Special handling for slide 3 (The Solution)
    if (scene === 'funnel') {
        startSlide3Animation()
    } else {
        stopSlide3Animation()
        if (sceneMap[scene]) {
            gsap.to(system.state, {
                ...sceneMap[scene],
                duration: 0.8,
                ease: "power2.inOut"
            })
        }
    }

    // Update particle color
    if (color) {
        system.setColor(color)
    }
}

// Detect scroll position to sync dots
function onScroll() {
    const scrollTop = container.scrollTop
    const slideHeight = window.innerHeight
    const newSlide = Math.round(scrollTop / slideHeight)

    if (newSlide !== currentSlide && newSlide >= 0 && newSlide < slides.length) {
        currentSlide = newSlide

        dots.forEach((dot, i) => {
            dot.classList.toggle('active', i === currentSlide)
        })

        // Update particles
        const scene = slides[currentSlide].dataset.scene
        const color = slides[currentSlide].dataset.color

        // Special handling for slide 3 (The Solution)
        if (scene === 'funnel') {
            startSlide3Animation()
        } else {
            stopSlide3Animation()
            if (sceneMap[scene]) {
                gsap.to(system.state, {
                    ...sceneMap[scene],
                    duration: 0.6,
                    ease: "power2.out"
                })
            }
        }

        if (color) {
            system.setColor(color)
        }
    }
}

container.addEventListener('scroll', onScroll, { passive: true })

// Arrow key navigation
document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
        e.preventDefault()
        goToSlide(currentSlide + 1)
    } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
        e.preventDefault()
        goToSlide(currentSlide - 1)
    }
})

// Initialize first slide
goToSlide(0)

// --- Render Loop ---
function tick() {
    system.update()
    system.draw()
    requestAnimationFrame(tick)
}

tick()
