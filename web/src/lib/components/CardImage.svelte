<script>
  import { settings } from '$lib/stores/settings';
  import { tick } from 'svelte';

  export let src = '';
  export let alt = '';
  export let hoverZoom = true;

  $: zoomPercent = $settings?.hover_zoom_percent ?? 150;

  let showPreview = false;
  let previewEl = null;
  let previewStyle = '';

  function handleMouseMove(e) {
    if (!hoverZoom || !src) return;
    const previewW = zoomPercent;
    const left = e.clientX - previewW / 2;
    const top = e.clientY - (zoomPercent * 1.5) - 16;
    previewStyle = `width: ${previewW}px; left: ${left}px; top: ${top}px;`;
    showPreview = true;
    tick().then(portalPreview);
  }

  function portalPreview() {
    if (previewEl && previewEl.parentNode !== document.body) {
      document.body.appendChild(previewEl);
    }
  }

  function handleMouseLeave() {
    showPreview = false;
    removePreview();
  }

  function removePreview() {
    if (previewEl && previewEl.parentNode) {
      previewEl.parentNode.removeChild(previewEl);
    }
  }
</script>

<div 
  class="card-image-wrapper" 
  class:hover-zoom={hoverZoom}
  on:mousemove={handleMouseMove}
  on:mouseleave={handleMouseLeave}
>
  <img {src} {alt} class="card-image" />
</div>
{#if showPreview && src}
  <div 
    class="card-hover-preview" 
    style={previewStyle}
    bind:this={previewEl}
  >
    <img {src} {alt} />
  </div>
{/if}

<style>
  .card-image-wrapper {
    position: relative;
    width: 100%;
    height: 100%;
  }

  .card-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 4px;
  }

  .card-hover-preview {
    position: fixed;
    aspect-ratio: 2/3;
    z-index: 99999;
    pointer-events: none;
    filter: drop-shadow(0 8px 24px rgba(0, 0, 0, 0.7));
  }

  .card-hover-preview img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 6px;
    border: 2px solid #ffd700;
  }

  .hover-zoom:hover .card-image {
    opacity: 0.7;
  }
</style>


