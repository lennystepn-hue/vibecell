<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from "vue";
import * as THREE from "three";

const canvasRef = ref<HTMLCanvasElement | null>(null);
let renderer: THREE.WebGLRenderer | null = null;
let animId = 0;

onMounted(() => {
  const canvas = canvasRef.value;
  if (!canvas) return;

  const W = canvas.clientWidth;
  const H = canvas.clientHeight;

  // Scene
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 100);
  camera.position.set(0, 0, 5);

  renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(W, H);
  renderer.setClearColor(0x000000, 0);
  renderer.shadowMap.enabled = false;

  // ── Octahedron geometry ──────────────────────────────────────────────
  const geo = new THREE.OctahedronGeometry(1.5, 0);

  // Wireframe overlay
  const wireMat = new THREE.MeshBasicMaterial({
    color: 0x5cc8a4,
    wireframe: true,
    transparent: true,
    opacity: 0.35,
  });
  const wireMesh = new THREE.Mesh(geo, wireMat);
  scene.add(wireMesh);

  // Solid faces — dark glass look
  const solidMat = new THREE.MeshPhongMaterial({
    color: 0x0d1a26,
    emissive: 0x071410,
    specular: 0x5cc8a4,
    shininess: 120,
    transparent: true,
    opacity: 0.55,
    side: THREE.DoubleSide,
    flatShading: true,
  });
  const solidMesh = new THREE.Mesh(geo, solidMat);
  scene.add(solidMesh);

  // ── Lights ────────────────────────────────────────────────────────────
  const ambient = new THREE.AmbientLight(0x8ab4ff, 0.4);
  scene.add(ambient);

  const pointA = new THREE.PointLight(0x5cc8a4, 3, 12);
  pointA.position.set(3, 4, 3);
  scene.add(pointA);

  const pointB = new THREE.PointLight(0x8ab4ff, 1.5, 10);
  pointB.position.set(-3, -2, 2);
  scene.add(pointB);

  // ── Particle halo ──────────────────────────────────────────────────────
  const particleCount = 280;
  const positions = new Float32Array(particleCount * 3);
  for (let i = 0; i < particleCount; i++) {
    const phi = Math.random() * Math.PI * 2;
    const theta = Math.random() * Math.PI;
    const r = 2.2 + Math.random() * 1.4;
    positions[i * 3] = r * Math.sin(theta) * Math.cos(phi);
    positions[i * 3 + 1] = r * Math.sin(theta) * Math.sin(phi);
    positions[i * 3 + 2] = r * Math.cos(theta);
  }
  const pgeo = new THREE.BufferGeometry();
  pgeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const pmat = new THREE.PointsMaterial({
    color: 0x5cc8a4,
    size: 0.018,
    transparent: true,
    opacity: 0.55,
  });
  const particles = new THREE.Points(pgeo, pmat);
  scene.add(particles);

  // ── Green glow ring ────────────────────────────────────────────────────
  const ringGeo = new THREE.TorusGeometry(2.05, 0.006, 8, 80);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0x5cc8a4,
    transparent: true,
    opacity: 0.18,
  });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 2;
  scene.add(ring);

  // ── Resize handler ────────────────────────────────────────────────────
  function onResize() {
    if (!canvas || !renderer) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  window.addEventListener("resize", onResize);

  // ── Animation loop ────────────────────────────────────────────────────
  let t = 0;
  function animate() {
    animId = requestAnimationFrame(animate);
    t += 0.004;

    wireMesh.rotation.y = t * 0.6;
    wireMesh.rotation.x = Math.sin(t * 0.3) * 0.3;
    solidMesh.rotation.y = t * 0.6;
    solidMesh.rotation.x = Math.sin(t * 0.3) * 0.3;
    particles.rotation.y = t * 0.15;
    ring.rotation.z = t * 0.2;

    // gentle bob
    wireMesh.position.y = Math.sin(t * 0.8) * 0.12;
    solidMesh.position.y = Math.sin(t * 0.8) * 0.12;

    // pulse glow
    pointA.intensity = 2.5 + Math.sin(t * 1.2) * 0.8;

    renderer!.render(scene, camera);
  }
  animate();

  // cleanup
  onBeforeUnmount(() => {
    cancelAnimationFrame(animId);
    window.removeEventListener("resize", onResize);
    renderer?.dispose();
  });
});
</script>

<template>
  <div class="relative w-full h-full">
    <!-- canvas fills parent -->
    <canvas ref="canvasRef" class="w-full h-full" />
    <!-- Radial green glow behind the diamond -->
    <div
      class="absolute inset-0 pointer-events-none"
      style="background: radial-gradient(ellipse 55% 55% at 50% 50%, rgba(92,200,164,0.08) 0%, transparent 70%)"
    />
  </div>
</template>
