import { useEffect, useRef, useCallback } from 'react';
import * as THREE from 'three';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useLenisInstance } from '@/hooks/useLenis';
import { Github } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

/* ─────────── 3D Wireframe Landscape ─────────── */
function WireframeLandscape() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let renderer: THREE.WebGLRenderer | null = null;
    let terrainGeometry: THREE.BufferGeometry | null = null;
    let terrainMaterial: THREE.LineBasicMaterial | null = null;
    let gridGeometry: THREE.BufferGeometry | null = null;
    let gridMaterial: THREE.LineBasicMaterial | null = null;
    let timeline: gsap.core.Timeline | null = null;
    let onResize: (() => void) | null = null;
    let resizeObserver: ResizeObserver | null = null;

    try {
      const isMobile = window.innerWidth < 768;
      const dpr = isMobile ? 0.5 : Math.min(window.devicePixelRatio, 1.25);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(
        60, Math.max(container.clientWidth, 1) / Math.max(container.clientHeight, 1), 0.1, 1000
      );
      camera.position.set(20, 12, 20);
      camera.lookAt(100, 0, 100);

      renderer = new THREE.WebGLRenderer({
        alpha: false,
        antialias: !isMobile,
        powerPreference: 'low-power',
      });
      renderer.setPixelRatio(dpr);
      renderer.setSize(Math.max(container.clientWidth, 1), Math.max(container.clientHeight, 1));
      renderer.setClearColor(0x030303, 1);
      renderer.domElement.style.width = '100%';
      renderer.domElement.style.height = '100%';
      renderer.domElement.style.display = 'block';
      container.appendChild(renderer.domElement);

      // Terrain
      const worldWidth = 200;
      const worldDepth = 200;
      const heightmap = new Uint8Array(worldWidth * worldDepth);

      const setHeight = (x: number, z: number, val: number) => {
        const cx = Math.max(0, Math.min(worldWidth - 1, Math.floor(x)));
        const cz = Math.max(0, Math.min(worldDepth - 1, Math.floor(z)));
        const idx = cz * worldWidth + cx;
        if (heightmap[idx] < val) heightmap[idx] = val;
      };

      const baseMountain = (xc: number, zc: number, radius: number, peakHeight: number) => {
        for (let i = Math.floor(xc - radius); i <= xc + radius; i++) {
          for (let k = Math.floor(zc - radius); k <= zc + radius; k++) {
            const dist = Math.sqrt((i - xc) ** 2 + (k - zc) ** 2);
            if (dist < radius) {
              const h = peakHeight * Math.pow(1 - dist / radius, 2);
              setHeight(i, k, h);
            }
          }
        }
      };

      const addRidge = (x1: number, z1: number, x2: number, z2: number, width: number, height: number) => {
        const dx = x2 - x1;
        const dz = z2 - z1;
        const len = Math.sqrt(dx * dx + dz * dz);
        const steps = Math.ceil(len * 2);
        for (let s = 0; s <= steps; s++) {
          const t = s / steps;
          const cx = x1 + dx * t;
          const cz = z1 + dz * t;
          const currentH = height * (1 - 2 * Math.abs(t - 0.5));
          for (let w = -width; w <= width; w++) {
            const distF = Math.abs(w) / width;
            const h = currentH * Math.pow(1 - distF, 2);
            if (h > 0) {
              const px = cx + w * (-dz / (len || 1));
              const pz = cz + w * (dx / (len || 1));
              setHeight(px, pz, h);
            }
          }
        }
      };

      baseMountain(80, 70, 45, 30);
      baseMountain(120, 110, 40, 28);
      baseMountain(50, 140, 35, 25);
      addRidge(80, 70, 120, 110, 12, 15);
      addRidge(120, 110, 160, 90, 10, 12);
      addRidge(80, 70, 50, 140, 14, 10);

      const vertices: number[] = [];
      const colors: number[] = [];
      const colorTop = new THREE.Color(0xffffff);
      const colorBottom = new THREE.Color(0x444444);

      for (let z = 0; z < worldDepth; z += 2) {
        for (let x = 0; x < worldWidth - 1; x += 2) {
          const h1 = heightmap[z * worldWidth + x] / 255 * 40;
          const h2 = heightmap[z * worldWidth + (x + 1)] / 255 * 40;
          vertices.push(x - worldWidth / 2, h1, z - worldDepth / 2);
          vertices.push(x + 1 - worldWidth / 2, h2, z - worldDepth / 2);
          colors.push(colorTop.r, colorTop.g, colorTop.b);
          const c2 = colorBottom.clone().lerp(colorTop, Math.min(h2 / 40, 1));
          colors.push(c2.r, c2.g, c2.b);
        }
      }
      for (let x = 0; x < worldWidth; x += 2) {
        for (let z = 0; z < worldDepth - 1; z += 2) {
          const h1 = heightmap[z * worldWidth + x] / 255 * 40;
          const h2 = heightmap[(z + 1) * worldWidth + x] / 255 * 40;
          vertices.push(x - worldWidth / 2, h1, z - worldDepth / 2);
          vertices.push(x - worldWidth / 2, h2, z + 1 - worldDepth / 2);
          colors.push(colorTop.r, colorTop.g, colorTop.b);
          const c2 = colorBottom.clone().lerp(colorTop, Math.min(h2 / 40, 1));
          colors.push(c2.r, c2.g, c2.b);
        }
      }

      terrainGeometry = new THREE.BufferGeometry();
      terrainGeometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
      terrainGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

      terrainMaterial = new THREE.LineBasicMaterial({
        vertexColors: true,
        color: 0xffffff,
        transparent: true,
        opacity: 0.92,
      });
      const terrain = new THREE.LineSegments(terrainGeometry, terrainMaterial);
      scene.add(terrain);

      // Grid plane
      const gridVertices: number[] = [];
      for (let x = -120; x <= 120; x += 2) {
        gridVertices.push(x, -1, -120, x, -1, 120);
      }
      for (let z = -120; z <= 120; z += 2) {
        gridVertices.push(-120, -1, z, 120, -1, z);
      }
      gridGeometry = new THREE.BufferGeometry();
      gridGeometry.setAttribute('position', new THREE.Float32BufferAttribute(gridVertices, 3));
      gridMaterial = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.05 });
      scene.add(new THREE.LineSegments(gridGeometry, gridMaterial));

      // Camera state for GSAP
      const camState = { x: 20, y: 12, z: 20, lx: 100, ly: 0, lz: 100 };

      const renderScene = () => {
        if (disposed || !renderer) return;
        camera.position.set(camState.x, camState.y, camState.z);
        camera.lookAt(camState.lx, camState.ly, camState.lz);
        renderer.render(scene, camera);
      };

      ScrollTrigger.getById('hero-wireframe-camera')?.kill();
      timeline = gsap.timeline({
        scrollTrigger: {
          id: 'hero-wireframe-camera',
          trigger: '#hero',
          start: 'top top',
          end: '+=200%',
          pin: true,
          scrub: 1,
          onUpdate: renderScene,
          onRefresh: renderScene,
        },
      });

      timeline.to(camState, { x: -30, y: 8, z: -10, lx: 50, ly: 5, lz: 50, ease: 'none', onUpdate: renderScene }, 0);
      timeline.to('#hero-content', { opacity: 0, y: -50, ease: 'none' }, 0);
      renderScene();

      onResize = () => {
        if (disposed || !renderer) return;
        const w = Math.max(container.clientWidth, 1);
        const h = Math.max(container.clientHeight, 1);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
        renderScene();
      };
      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => onResize?.());
        resizeObserver.observe(container);
      }
      window.addEventListener('resize', onResize);
    } catch (err) {
      console.warn('3D scene init failed:', err);
    }

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      if (onResize) window.removeEventListener('resize', onResize);
      timeline?.kill();
      if (renderer?.domElement?.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
      terrainGeometry?.dispose();
      terrainMaterial?.dispose();
      gridGeometry?.dispose();
      gridMaterial?.dispose();
      renderer?.dispose();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ position: 'absolute', inset: 0, zIndex: 0, background: 'radial-gradient(ellipse at center, #0a0a0a 0%, #030303 100%)' }}
    />
  );
}

/* ─────────── Kinetic Headline ─────────── */
function KineticHeadline({ text, delay = 0.5 }: { text: string; delay?: number }) {
  const words = text.split(' ');

  return (
    <h1
      className="font-heading text-[46px] font-bold leading-[0.95] text-zink sm:text-[70px] lg:text-[92px] xl:text-[104px]"
      style={{
        perspective: '400px',
        textShadow: '0 8px 28px rgba(0,0,0,0.75)',
      }}
    >
      {words.map((word, i) => (
        <span
          key={i}
          className="inline-block whitespace-nowrap"
          style={{
            transformOrigin: 'bottom center',
            animation: `kineticReveal 0.7s ${delay + i * 0.08}s cubic-bezier(0.34, 1.56, 0.64, 1) forwards`,
            opacity: 0,
          }}
        >
          {word}{i < words.length - 1 ? '\u00A0' : ''}
        </span>
      ))}
    </h1>
  );
}

/* ─────────── Hero Section ─────────── */
export default function HeroSection() {
  const lenis = useLenisInstance();

  const scrollTo = useCallback((id: string) => {
    if (lenis) {
      lenis.scrollTo(id);
    } else {
      const el = document.querySelector(id);
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  }, [lenis]);

  return (
    <section id="hero" className="relative min-h-screen overflow-hidden bg-zbg supports-[height:100svh]:min-h-[100svh]">
      <WireframeLandscape />

      <div className="pointer-events-none absolute inset-0 z-[1] bg-[radial-gradient(ellipse_at_center,rgba(0,0,0,0.18)_0%,rgba(0,0,0,0.38)_58%,rgba(0,0,0,0.72)_100%)]" />

      <div
        id="hero-content"
        className="relative z-[2] flex min-h-screen flex-col items-center justify-center px-6 text-center supports-[height:100svh]:min-h-[100svh]"
      >
        <div className="max-w-[900px]">
          <p
            className="text-eyebrow text-zlime mb-6"
            style={{ animation: 'fadeSlideUp 0.6s 0.3s ease-out forwards', opacity: 0 }}
          >
            Open-source local memory for agents
          </p>

          <KineticHeadline text="Agent memory you can verify." delay={0.5} />

          <p
            className="mx-auto mt-6 max-w-[640px] text-[17px] leading-relaxed text-[#D8D8D8] max-sm:hidden"
            style={{ animation: 'fadeSlideUp 0.6s 0.8s ease-out forwards', opacity: 0, textShadow: '0 4px 18px rgba(0,0,0,0.9)' }}
          >
            Local-first memory for AI agents. Request approved memories, propose new facts,
            and verify what actually shaped the next action.
          </p>

          <p
            className="mx-auto mt-6 max-w-[320px] text-[17px] leading-relaxed text-[#D8D8D8] sm:hidden"
            style={{ animation: 'fadeSlideUp 0.6s 0.8s ease-out forwards', opacity: 0, textShadow: '0 4px 18px rgba(0,0,0,0.9)' }}
          >
            Local memory for agents. Receipts for what shaped the work.
          </p>

          <p
            className="mx-auto mt-4 hidden max-w-[600px] text-[14px] leading-relaxed text-[#AFAFAF] sm:block"
            style={{ animation: 'fadeSlideUp 0.6s 0.9s ease-out forwards', opacity: 0, textShadow: '0 4px 18px rgba(0,0,0,0.9)' }}
          >
            Receipts show what was used, what was withheld, and the Merkle root behind the action.
            Treeship can publish a public proof URL when needed.
          </p>

          <div
            className="mt-10 flex flex-wrap items-center justify-center gap-4"
            style={{ animation: 'fadeSlideUp 0.5s 1.0s ease-out forwards', opacity: 0 }}
          >
            <button
              onClick={() => scrollTo('#install')}
              className="rounded-full bg-zlime px-8 py-3.5 text-cta text-[#030303] transition-all duration-150 hover:bg-[#7BC45A] hover:scale-[1.03] hover:shadow-[0_0_24px_rgba(146,214,111,0.3)]"
            >
              Install ZMem
            </button>
            <button
              onClick={() => { window.location.href = '/proof'; }}
              className="rounded-full border border-zline bg-transparent px-8 py-3.5 text-cta text-zink transition-all duration-150 hover:border-zlime hover:text-zlime"
            >
              View Proof Matrix
            </button>
            <a
              href="https://github.com/zerkerlabs/zmem"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full border border-zline bg-transparent px-8 py-3.5 text-cta text-zink transition-all duration-150 hover:border-zlime hover:text-zlime"
            >
              <Github size={16} />
              GitHub
            </a>
          </div>
        </div>

        <div
          className="absolute bottom-10 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2"
          style={{ animation: 'scrollIndicatorFade 0.5s 3s ease-out forwards' }}
        >
          <div className="relative h-10 w-px bg-zmuted">
            <div
              className="absolute left-1/2 top-0 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-zlime"
              style={{ animation: 'scrollPulseDot 2s ease-in-out infinite' }}
            />
          </div>
          <span className="text-caption text-zdim">Scroll</span>
        </div>
      </div>
    </section>
  );
}
