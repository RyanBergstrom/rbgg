<script>
  let { label, tone = 'warn', compact = false } = $props();
</script>

<span
  class={`counter-flag counter-flag--${tone}${compact ? ' counter-flag--compact' : ''}`}
  title={label}
  aria-label={label}
>{label}</span>

<style>
  .counter-flag {
    position: absolute;
    top: 1px;
    left: 50%;
    z-index: 20;
    transform: translateX(-50%);
    max-width: 64px;
    padding: 1px 4px;
    border: 1px solid rgba(255, 255, 255, 0.85);
    border-radius: 3px;
    background: #c94b1f;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.75);
    color: #fff;
    font-size: 7px;
    font-weight: 800;
    letter-spacing: 0.05em;
    line-height: 1.1;
    text-align: center;
    text-transform: uppercase;
    white-space: nowrap;
    pointer-events: none;
  }

  .counter-flag--compact {
    max-width: 42px;
    padding: 0 3px;
    font-size: 6px;
    letter-spacing: 0.02em;
  }

  .counter-flag--warn {
    background: #c94b1f;
  }

  .counter-flag--danger {
    background: #8b1e1e;
  }

  .counter-flag--info {
    background: #2f6b9e;
  }
</style>
