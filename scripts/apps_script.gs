/**
 * Pierre-ai — pont Google Sheet ↔ backend du pipeline.
 *
 * Feuille attendue (ligne 1 = en-têtes) :
 *   A: ID        (ex. demo-5terres — sans espace, sans accent)
 *   B: URL       (site de l'hôtel, ex. https://5terres-hotel.fr/fr/)
 *   C: Statut    (nouveau → envoyé → en cours → prêt / erreur)
 *   D: Lien demo (rempli automatiquement par le webhook)
 *
 * À renseigner dans Propriétés du script (icône roue dentée) :
 *   BACKEND_URL    = https://<ton-backend>.fly.dev        (sans / final)
 *   PIPELINE_TOKEN = même valeur que PIPELINE_TOKEN du .env du backend
 */

const COL_ID = 1, COL_URL = 2, COL_STATUT = 3, COL_LIEN = 4;

function props() {
  const p = PropertiesService.getScriptProperties();
  return { back: p.getProperty("BACKEND_URL"), token: p.getProperty("PIPELINE_TOKEN") };
}

/** Nouvelle ligne remplie (ID + URL) → on envoie au backend. */
function onEdit(e) {
  if (!e || !e.range) return;
  const sheet = e.range.getSheet();
  if (sheet.getName() !== "Imports") return;
  const row = e.range.getRow();
  if (row === 1) return; // en-têtes
  const values = sheet.getRange(row, COL_ID, 1, 4).getValues()[0];
  const [id, url, statut] = values;
  if (!id || !url) return;
  if (statut && statut !== "nouveau") return; // déjà traité
  if (e.range.getColumn() !== COL_ID && e.range.getColumn() !== COL_URL) return;

  const { back, token } = props();
  const res = UrlFetchApp.fetch(back + "/import", {
    method: "post",
    contentType: "application/json",
    headers: { "X-Pipeline-Token": token },
    payload: JSON.stringify({ id: id, url: url }),
    muteHttpExceptions: true,
  });
  sheet.getRange(row, COL_STATUT).setValue(res.getResponseCode() === 202 ? "envoyé" : "erreur: " + res.getContentText());
}

/** Webhook appelé par le backend à la fin du traitement : {"ID": ..., "lien demo": ...} */
function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Imports");
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][COL_ID - 1] === body.ID) {
      sheet.getRange(i + 1, COL_STATUT).setValue("prêt");
      if (body["lien demo"]) sheet.getRange(i + 1, COL_LIEN).setValue(body["lien demo"]);
      return ContentService.createTextOutput(JSON.stringify({ ok: true }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }
  return ContentService.createTextOutput(JSON.stringify({ ok: false, raison: "ID introuvable" }))
    .setMimeType(ContentService.MimeType.JSON);
}

/** Test manuel depuis l'éditeur Apps Script. */
function doGet() {
  return ContentService.createTextOutput("pierre-ai webhook OK");
}

/** Crée le déclencheur onEdit automatiquement (une seule fois). */
function installer() {
  ScriptApp.newTrigger("onEdit").forSpreadsheet(SpreadsheetApp.getActive()).onEdit().create();
}
