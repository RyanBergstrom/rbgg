
// this file is generated — do not edit it


declare module "svelte/elements" {
	export interface HTMLAttributes<T> {
		'data-sveltekit-keepfocus'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-noscroll'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-preload-code'?:
			| true
			| ''
			| 'eager'
			| 'viewport'
			| 'hover'
			| 'tap'
			| 'off'
			| undefined
			| null;
		'data-sveltekit-preload-data'?: true | '' | 'hover' | 'tap' | 'off' | undefined | null;
		'data-sveltekit-reload'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-replacestate'?: true | '' | 'off' | undefined | null;
	}
}

export {};


declare module "$app/types" {
	type MatcherParam<M> = M extends (param : string) => param is (infer U extends string) ? U : string;

	export interface AppTypes {
		RouteId(): "/" | "/asset-reviewer" | "/games" | "/games/[gameId]" | "/games/[gameId]/play" | "/games/[gameId]/setup" | "/horizon-tree";
		RouteParams(): {
			"/games/[gameId]": { gameId: string };
			"/games/[gameId]/play": { gameId: string };
			"/games/[gameId]/setup": { gameId: string }
		};
		LayoutParams(): {
			"/": { gameId?: string | undefined };
			"/asset-reviewer": Record<string, never>;
			"/games": { gameId?: string | undefined };
			"/games/[gameId]": { gameId: string };
			"/games/[gameId]/play": { gameId: string };
			"/games/[gameId]/setup": { gameId: string };
			"/horizon-tree": Record<string, never>
		};
		Pathname(): "/" | "/asset-reviewer" | `/games/${string}/play` & {} | `/games/${string}/setup` & {} | "/horizon-tree";
		ResolvedPathname(): `${"" | `/${string}`}${ReturnType<AppTypes['Pathname']>}`;
		Asset(): "/bus-game-board.png" | string & {};
	}
}