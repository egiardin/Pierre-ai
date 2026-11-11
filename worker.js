// Worker « assets only » : il ne fait que servir le build statique (web/dist).
// Le fallback SPA est géré par wrangler.toml (not_found_handling), qui renvoie
// index.html pour studio.pierre-ai.fr/{id-dossier}.
export default {
  fetch(request, env) {
    return env.ASSETS.fetch(request);
  },
};
