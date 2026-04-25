import { ShapeManager } from './shape-manager.js'

export class ParticleSystem {
    constructor(canvas) {
        this.ctx = canvas.getContext('2d')
        this.width = canvas.width
        this.height = canvas.height
        this.particles = []
        this.count = 500 // Increased count for better shapes

        this.shapeManager = new ShapeManager(this.width, this.height)

        this.noiseScale = 0.005
        this.zOffset = 0

        this.state = {
            chaos: 0,
            flowConfig: 0,
            pressure: 0,
            failureMode: 0,
            stability: 0,
            looping: 0,
            shapeInfluence: 0, // 0 = physics/random, 1 = strict shape
            currentShape: 'grid',
            globalSpeed: 1 // 1 = normal, 0.2 = reading mode
        }

        // Current particle color (transitions smoothly)
        this.currentColor = '#4a90e2'
        this.targetColor = '#4a90e2'

        this.initParticles()
    }

    resize(width, height) {
        this.width = width
        this.height = height
        this.shapeManager.resize(width, height)
    }

    initParticles() {
        this.particles = []
        for (let i = 0; i < this.count; i++) {
            this.particles.push({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                vx: 0,
                vy: 0,
                life: 1,
                dead: false,
                dying: false,
                index: i
            })
        }
    }

    updateState(newState) {
        Object.assign(this.state, newState)
        if (newState.currentShape) {
            this.shapeManager.currentShape = newState.currentShape
        }
    }

    setColor(hex) {
        this.targetColor = hex
    }

    // Interpolate hex colors
    lerpColor(a, b, t) {
        const ah = parseInt(a.replace('#', ''), 16)
        const bh = parseInt(b.replace('#', ''), 16)
        const ar = ah >> 16, ag = (ah >> 8) & 0xff, ab = ah & 0xff
        const br = bh >> 16, bg = (bh >> 8) & 0xff, bb = bh & 0xff
        const rr = ar + (br - ar) * t
        const rg = ag + (bg - ag) * t
        const rb = ab + (bb - ab) * t
        return `rgb(${Math.round(rr)}, ${Math.round(rg)}, ${Math.round(rb)})`
    }

    update() {
        // Slower time in reading mode
        this.zOffset += (0.005 + (this.state.chaos * 0.02)) * this.state.globalSpeed

        // Loop Pulse
        let loopFactor = 0
        if (this.state.looping > 0.5) {
            loopFactor = Math.sin(performance.now() * 0.003)
        }

        const center = { x: this.width / 2, y: this.height / 2 }

        this.particles.forEach(p => {
            // Respawning
            if (p.dead) {
                if (Math.random() < 0.05) {
                    p.dead = false; p.dying = false; p.life = 1;
                    p.x = Math.random() * this.width; p.y = -20;
                }
                return
            }

            // Dying animation
            if (p.dying) {
                p.life -= 0.05
                if (p.life <= 0) p.dead = true
            }

            // Failure trigger
            if (this.state.failureMode > 0 && !p.dying) {
                if (Math.random() < 0.002 * this.state.failureMode) p.dying = true
            }

            let ax = 0
            let ay = 0

            // 1. Shape Steering
            if (this.state.shapeInfluence > 0) {
                let target = this.shapeManager.getTarget(p.index, this.count)

                // ROTATION FOR LOOP
                if (this.state.currentShape === 'loop') {
                    // Rotate target around center (VERY SLOW - 10x slower than original)
                    const time = performance.now() * 0.0001
                    const dx = target.x - center.x
                    const dy = target.y - center.y
                    const angle = Math.atan2(dy, dx) + time
                    const r = Math.sqrt(dx * dx + dy * dy)
                    target = {
                        x: center.x + Math.cos(angle) * r,
                        y: center.y + Math.sin(angle) * r
                    }
                }

                // Pulse interaction
                if (this.state.looping > 0.5) {
                    const dist = p.x - center.x
                    target.x += dist * loopFactor * 0.3
                }

                // Spring force to target
                const dx = target.x - p.x
                const dy = target.y - p.y

                // Loose following vs strict snapping
                const strength = 0.05 * this.state.shapeInfluence
                ax += dx * strength
                ay += dy * strength
            }

            // 2. Physics/Flow Layer (The "Motion" layer)
            // Always apply some gravity/flow unless shape is 100% rigid (determinism)
            if (this.state.shapeInfluence < 0.8 || this.state.chaos > 0) {
                // Noise flow
                const angle = Math.sin(p.x * 0.005 + this.zOffset) * Math.PI * 2
                const flowX = Math.cos(angle)
                const flowY = Math.sin(angle)

                ax += flowX * this.state.chaos * 0.5
                ay += flowY * this.state.chaos * 0.5 + 0.1 // Gravity
            }

            // 3. Pressure (Walls) - independent of shape
            if (this.state.pressure > 0) {
                const margin = this.width * 0.3 * this.state.pressure
                if (p.x < margin) ax += 0.5
                if (p.x > this.width - margin) ax -= 0.5
            }

            // Integration with Speed Control
            p.vx += ax
            p.vy += ay

            // Apply Speed Limit / Dampening
            p.vx *= 0.92 // Friction
            p.vy *= 0.92

            // Move
            p.x += p.vx * this.state.globalSpeed
            p.y += p.vy * this.state.globalSpeed

            // Bounds (Soft wrap or hard wall?)
            // If strictly creating a shape, allow them to stay. 
            // If flowing, wrap.
            if (this.state.shapeInfluence < 0.5) {
                if (p.y > this.height) { p.y = 0; p.x = Math.random() * this.width }
                if (p.x > this.width) p.x = 0;
                if (p.x < 0) p.x = this.width;
            }
        })
    }

    // Draw stays same mostly, maybe nicer glows
    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height)

        // Dynamic Connecting Lines (if shape is tight like grid)
        // Optimization: only draw lines if high shape influence

        this.particles.forEach(p => {
            if (p.dead) return

            // Basic Draw
            this.ctx.globalAlpha = p.life * (0.4 + this.state.shapeInfluence * 0.6)

            // Smoothly transition to target color
            this.currentColor = this.lerpColor(this.currentColor.startsWith('#') ? this.currentColor : '#4a90e2', this.targetColor, 0.05)

            // Color - use section color, override for dying particles
            if (p.dying) this.ctx.fillStyle = '#d0021b'
            else this.ctx.fillStyle = this.currentColor

            this.ctx.beginPath()
            // Square particles for grid? Round for others?
            if (this.state.currentShape === 'grid' && this.state.shapeInfluence > 0.8) {
                this.ctx.rect(p.x - 2, p.y - 2, 4, 4)
            } else {
                this.ctx.arc(p.x, p.y, 2, 0, Math.PI * 2)
            }
            this.ctx.fill()
        })
        this.ctx.globalAlpha = 1
    }
}
