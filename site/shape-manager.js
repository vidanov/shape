export class ShapeManager {
    constructor(width, height) {
        this.width = width
        this.height = height
        this.currentShape = 'grid' // grid, cloud, funnel, beam
    }

    resize(w, h) {
        this.width = w
        this.height = h
    }

    // Returns a target {x, y} for a particle index
    getTarget(index, totalParticles) {
        const cx = this.width / 2
        const cy = this.height / 2

        switch (this.currentShape) {
            case 'grid':
                return this.getGridTarget(index, totalParticles, cx, cy)
            case 'cloud':
                return this.getCloudTarget(index, totalParticles, cx, cy)
            case 'funnel':
                return this.getFunnelTarget(index, totalParticles, cx, cy)
            case 'beam':
                return this.getBeamTarget(index, totalParticles, cx, cy)
            case 'loop':
                return this.getLoopTarget(index, totalParticles, cx, cy)
            default:
                return { x: Math.random() * this.width, y: Math.random() * this.height }
        }
    }

    getGridTarget(index, total, cx, cy) {
        // 3D-ish Grid or Chip
        const cols = 20
        const spacing = 30
        const row = Math.floor(index / cols)
        const col = index % cols
        // Center the grid
        const gridWidth = cols * spacing
        const gridHeight = (total / cols) * spacing
        return {
            x: cx - gridWidth / 2 + col * spacing,
            y: cy - gridHeight / 2 + row * spacing
        }
    }

    getCloudTarget(index, total, cx, cy) {
        // Random point in sphere
        const angle = Math.random() * Math.PI * 2
        const radius = Math.random() * 20
        return {
            x: cx + Math.cos(angle) * (200 + Math.random() * 50),
            y: cy + Math.sin(angle) * (200 + Math.random() * 50)
        }
    }

    getLoopTarget(index, total, cx, cy) {
        // A visual feedback loop: Circle that spirals in
        const angle = (index / total) * Math.PI * 2 * 3 // 3 windings
        // Radius depends on index (outer to inner)
        const radius = 200 - (index / total) * 150

        // Add time-based rotation in ParticleSystem, but base target is spiral
        return {
            x: cx + Math.cos(angle) * radius,
            y: cy + Math.sin(angle) * radius
        }
    }

    getFunnelTarget(index, total, cx, cy) {
        // Funnel shape: wide top, narrow bottom
        // We can map particles to a function y = x^2 approx
        const y = (index / total) * this.height // Spread vertically
        // Width at this y:
        // y=0 -> width big
        // y=height -> width small
        const progress = index / total
        const widthAtY = 300 * (1 - progress) + 30 // taper to 30px (tighter)
        const xOffset = (Math.random() - 0.5) * widthAtY
        return {
            x: cx + xOffset,
            y: (this.height * 0.2) + progress * (this.height * 0.6) // Middle of screen
        }
    }

    getBeamTarget(index, total, cx, cy) {
        // Tight horizontal beam or vertical stream?
        // Let's go vertical stream for stability
        const width = 40
        const xOffset = (Math.random() - 0.5) * width
        const y = (index / total) * this.height
        return {
            x: cx + xOffset,
            y: y
        }
    }
}
