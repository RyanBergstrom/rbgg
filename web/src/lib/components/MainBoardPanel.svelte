<script>
  import { onMount } from 'svelte';

  export let topology = 'grid';
  export let initialTopology = 'grid';
  export let initialSize = 8;

  let cells = [];
  let size = 8;

  function generateCells() {
    cells = [];
    const topologies = {
      grid: () => {
        for (let r = 0; r < size; r++) {
          for (let c = 0; c < size; c++) {
            cells.push({ r, c, type: 'grid' });
          }
        }
      },
      hex: () => {
        for (let r = 0; r < size; r++) {
          for (let q = 0; q < size; q++) {
            cells.push({ r, q, type: 'hex' });
          }
        }
      },
      graph: () => {
        for (let i = 0; i < size * 2; i++) {
          cells.push({ id: i, type: 'graph' });
        }
      }
    };

    const topoFn = topologies[topology] || topologies.grid;
    topoFn();
  }

  onMount(() => {
    if (initialTopology !== topology) {
      topology = initialTopology;
    }
    if (initialSize !== size) {
      size = initialSize;
    }
    generateCells();
  });

  $: if (topology || size) {
    generateCells();
  }
</script>

<div class="main-board-panel"
     class:grid={topology === 'grid'}
     class:hex={topology === 'hex'}
     class:graph={topology === 'graph'}>
  <div class="board-header">
    <span class="board-title">Board ({topology})</span>
    <span class="board-size">Size: {size}x{size}</span>
  </div>

  <div class="board-grid">
    {#each cells as cell (cell.id || `${cell.r}-${cell.q}`)}
      <div class="board-cell"
           class:grid-cell={cell.type === 'grid'}
           class:hex-cell={cell.type === 'hex'}
           class:graph-node={cell.type === 'graph'}
           aria-role={cell.type}
           aria-label={`Board cell at ${cell.r}, ${cell.q || cell.id}`}>
        {#if cell.type === 'grid'}
          <span>{cell.c}</span>
        {:else if cell.type === 'hex'}
          <span>{cell.q}</span>
        {:else if cell.type === 'graph'}
          <span>{cell.id}</span>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .main-board-panel {
    width: 100%;
    max-width: 800px;
    margin: 1rem auto;
    font-family: system-ui, sans-serif;
  }

  .board-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #ddd;
  }

  .board-title {
    font-weight: bold;
    font-size: 1.1rem;
  }

  .board-size {
    font-size: 0.9rem;
    color: #666;
  }

  .board-grid {
    display: grid;
    gap: 4px;
  }

  .main-board-panel.grid .board-grid {
    grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
  }

  .main-board-panel.hex .board-grid {
    grid-template-columns: repeat(auto-fill, minmax(35px, 1fr));
  }

  .main-board-panel.graph .board-grid {
    grid-template-columns: repeat(auto-fill, minmax(30px, 1fr));
  }

  .board-cell {
    aspect-ratio: 1;
    background: #fff;
    border: 1px solid #ddd;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    color: #333;
  }

  .board-cell.hex-cell {
    shape-outside: inset(50% 25% 50% 25%);
  }

  .board-cell.graph-node {
    aspect-ratio: 1;
  }
</style>
