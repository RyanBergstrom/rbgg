export const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set([]),
	mimeTypes: {},
	_: {
		client: {start:"_app/immutable/entry/start.BRXxXsjH.js",app:"_app/immutable/entry/app.Bu6waC0S.js",imports:["_app/immutable/entry/start.BRXxXsjH.js","_app/immutable/chunks/AcgoXiYk.js","_app/immutable/chunks/D84Y2HP9.js","_app/immutable/chunks/BAsstkaf.js","_app/immutable/entry/app.Bu6waC0S.js","_app/immutable/chunks/C1FmrZbK.js","_app/immutable/chunks/D84Y2HP9.js","_app/immutable/chunks/DZt3FjrX.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('./nodes/0.js')),
			__memo(() => import('./nodes/1.js')),
			__memo(() => import('./nodes/2.js')),
			__memo(() => import('./nodes/3.js')),
			__memo(() => import('./nodes/4.js'))
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
				id: "/games/[gameId]/play",
				pattern: /^\/games\/([^/]+?)\/play\/?$/,
				params: [{"name":"gameId","optional":false,"rest":false,"chained":false}],
				page: { layouts: [0,], errors: [1,], leaf: 3 },
				endpoint: null
			},
			{
				id: "/games/[gameId]/setup",
				pattern: /^\/games\/([^/]+?)\/setup\/?$/,
				params: [{"name":"gameId","optional":false,"rest":false,"chained":false}],
				page: { layouts: [0,], errors: [1,], leaf: 4 },
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
