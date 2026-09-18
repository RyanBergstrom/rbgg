
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
		RouteId(): "/" | "/games" | "/games/[gameId]" | "/games/[gameId]/play" | "/games/[gameId]/setup";
		RouteParams(): {
			"/games/[gameId]": { gameId: string };
			"/games/[gameId]/play": { gameId: string };
			"/games/[gameId]/setup": { gameId: string }
		};
		LayoutParams(): {
			"/": { gameId?: string | undefined };
			"/games": { gameId?: string | undefined };
			"/games/[gameId]": { gameId: string };
			"/games/[gameId]/play": { gameId: string };
			"/games/[gameId]/setup": { gameId: string }
		};
		Pathname(): "/" | `/games/${string}/play` & {} | `/games/${string}/setup` & {};
		ResolvedPathname(): `${"" | `/${string}`}${ReturnType<AppTypes['Pathname']>}`;
		Asset(): string & {};
	}
}