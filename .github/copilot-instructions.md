# Copilot Instructions

## Project Guidelines
- When running long data-enrichment scripts, persist each successful result to the target file immediately so interrupted runs retain completed work.
- Long-running candidate download scripts must resume from the next unprocessed item rather than retrying earlier items that returned no results.
- Approved photographs must be stored in hits.htm as Internet URLs, not as local asset paths.
- Use modern official Belarusian orthography, not Taraškievica, for Belarusian translations in this project.
- When providing Google Cloud commands for this project, use project ID belarus-districts-game-123456.

## Search Instructions
- For location photo searches, simplify an item title containing a settlement (for example, remove 'в д.' and do not append the district) so the query is like 'Троицкий костёл Ишколдь'.