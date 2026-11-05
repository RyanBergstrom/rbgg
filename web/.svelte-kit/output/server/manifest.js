export const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set(["bus-game-board.png"]),
	mimeTypes: {".png":"image/png"},
	_: {
		client: {start:"_app/immutable/entry/start.Chx_5Deo.js",app:"_app/immutable/entry/app.DuKWbGUf.js",imports:["_app/immutable/entry/start.Chx_5Deo.js","_app/immutable/chunks/2JmmnmuR.js","_app/immutable/chunks/5JXyHpLP.js","_app/immutable/chunks/Cak6kzeI.js","_app/immutable/chunks/BJiQFusM.js","_app/immutable/entry/app.DuKWbGUf.js","_app/immutable/chunks/5JXyHpLP.js","_app/immutable/chunks/BJiQFusM.js","_app/immutable/chunks/uBIymjUX.js","_app/immutable/chunks/xihTtKlq.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./nodes/0.js')),
			__memo(() => import('./nodes/1.js')),
			__memo(() => import('./nodes/2.js')),
			__memo(() => import('./nodes/3.js')),
			__memo(() => import('./nodes/4.js')),
			__memo(() => import('./nodes/5.js')),
			__memo(() => import('./nodes/6.js'))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/",
				pattern: /^\/$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			},
			{
				id: "/asset-reviewer",
				pattern: /^\/asset-reviewer\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 3 },
				endpoint: null
			},
			{
				id: "/games/[gameId]/play",
				pattern: /^\/games\/([^/]+?)\/play\/?$/,
				params: [{"name":"gameId","optional":false,"rest":false,"chained":false}],
				page: { layouts: [0,], errors: [1,], leaf: 4 },
				endpoint: null
			},
			{
				id: "/games/[gameId]/setup",
				pattern: /^\/games\/([^/]+?)\/setup\/?$/,
				params: [{"name":"gameId","optional":false,"rest":false,"chained":false}],
				page: { layouts: [0,], errors: [1,], leaf: 5 },
				endpoint: null
			},
			{
				id: "/horizon-tree",
				pattern: /^\/horizon-tree\/?$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 6 },
				endpoint: null
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();
