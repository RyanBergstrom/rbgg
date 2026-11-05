<script>
  import TwilightStruggleBoard from '../../src/lib/components/games/twilight_struggle/TwilightStruggleBoard.svelte';

  export let screenState;
  let capturedMove = null;

  function capture(event) {
    capturedMove = event.detail;
  }
</script>

<TwilightStruggleBoard {screenState} on:select-move={capture} />
{#if capturedMove}
  <output data-testid="captured-move">{JSON.stringify(capturedMove)}</output>
{/if}
