import argparse
import asyncio
from .extractor import extract_site

parser = argparse.ArgumentParser(
    description="Extraire au maximum 99 photos et les textes d’un site hôtelier."
)
parser.add_argument("url", help="URL HTTP(S) du site")
args = parser.parse_args()
try:
    asyncio.run(extract_site(args.url))
except (ValueError, RuntimeError, OSError) as error:
    parser.exit(1, f"Erreur : {error}\n")

except KeyboardInterrupt:
    parser.exit(130, "Extraction interrompue ; résultats partiels conservés.\n")
