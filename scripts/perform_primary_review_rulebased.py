#!/usr/bin/env python3
"""
Primary Review - 5 Judge System (Rule-Based Implementation)
Evaluates SaaS title suitability with 5 independent judges

Updated per latest agent specs:
- Repeated chars: 3+ consecutive only (lee, all, bob, off are OK)
- Generic words: explicit rejection for pronouns, articles, prepositions, auxiliary verbs
- Geographic names: explicit rejection
- Labels: strict functional/brandable/ambiguous classification
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any

# Generic words that should be explicitly rejected (47 words - filtered by rule_screener)
# These are NOT checked here since rule_screener already filtered them
# This list is kept for reference only
GENERIC_WORDS_REFERENCE = {
    'a', 'an', 'the', 'and', 'or', 'but', 'for', 'nor', 'so', 'yet',
    'i', 'me', 'my', 'we', 'us', 'our', 'you', 'your', 'he', 'him', 'his',
    'she', 'her', 'it', 'its', 'they', 'them', 'their', 'this', 'that',
    'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
    'had', 'having', 'do', 'does', 'did', 'doing', 'can', 'could', 'will',
    'would', 'shall', 'should', 'may', 'might', 'must'
}

# Additional generic words not in rule_screener (for completeness here)
GENERIC_WORDS_ADDITIONAL = {
    'mine', 'myself', 'yourself', 'yourselves', 'himself', 'herself', 'itself',
    'ourselves', 'themselves', 'these', 'those', 'who', 'whom', 'whose', 'which', 'what',
    'about', 'above', 'across', 'after', 'against', 'along', 'among', 'around', 'at',
    'before', 'behind', 'below', 'beneath', 'beside', 'between', 'beyond', 'by',
    'down', 'during', 'except', 'from', 'in', 'inside', 'into', 'of', 'off',
    'on', 'onto', 'out', 'outside', 'over', 'past', 'since', 'through', 'throughout',
    'to', 'toward', 'under', 'underneath', 'until', 'up', 'upon', 'with', 'within', 'without',
    'although', 'because', 'unless', 'while', 'where', 'whereas', 'whether',
    'very', 'too', 'also', 'just', 'then', 'there', 'here', 'now', 'always', 'never',
    'often', 'sometimes', 'still', 'already', 'again', 'away', 'back', 'even', 'ever',
    'good', 'bad', 'big', 'small', 'little', 'old', 'new', 'young', 'high', 'low',
    'long', 'short', 'right', 'wrong', 'same', 'different', 'all', 'some', 'many', 'much',
    'few', 'more', 'most', 'such', 'own', 'other', 'another', 'both', 'each', 'every',
    'thing', 'something', 'nothing', 'anything', 'someone', 'anyone', 'everyone', 'one',
    'body', 'time', 'day', 'year', 'way', 'part', 'place', 'case', 'fact', 'kind',
    'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'first', 'second', 'third', 'once', 'twice',
}

# Non-English words to reject (expanded per latest spec)
SPANISH_WORDS = {
    'que', 'corra', 'voz', 'luchar', 'adios', 'amigos', 'alabadle', 'alarma', 'alfaro',
    'vive', 'carajo', 'alla', 'tu', 'alo', 'presidente', 'ama', 'arriba', 'pachanga',
    'atame', 'caramba', 'carmela', 'basta', 'ya', 'bastardos', 'vivo', 'bienvenido',
    'marshall', 'ciauetistico', 'ciautistico', 'dame', 'decapitacion', 'deladap',
    'dos', 'explora', 'dios', 'sabe', 'por', 'matar', 'vanidad', 'ganas', 'asi',
    'jardin', 'donde', 'flores', 'llueven', 'sobre', 'rostros', 'muertos', 'gritar',
    'silencio', 'llorar', 'lagrimas', 'sangre', 'amor', 'odio', 'muerte', 'vida',
    'paz', 'guerra', 'libertad', 'justicia', 'su', 'dov', 'ak', 'tovarisch', 'version',
    'original', 'nada', 'mas', 'mi', 'es', 'un', 'los', 'las', 'el', 'ella', 'ellos',
    'nos', 'nosotros', 'vosotros', 'vosotras', 'les', 'les', 'lo', 'la', 'le', 'me',
    'te', 'se', 'nos', 'os', 'mi', 'ti', 'si', 'conmigo', 'contigo', 'consigo',
    'este', 'esta', 'esto', 'estos', 'estas', 'ese', 'esa', 'eso', 'esos', 'esas',
    'aquel', 'aquella', 'aquello', 'aquellos', 'aquellas', 'quien', 'quienes', 'cuyo',
    'cuya', 'cuyos', 'cuyas', 'cuanto', 'cuanta', 'cuantos', 'cuantas', 'alguno',
    'alguna', 'algunos', 'algunas', 'ninguno', 'ninguna', 'ningunos', 'ningunas',
    'todo', 'toda', 'todos', 'todas', 'mucho', 'mucha', 'muchos', 'muchas', 'poco',
    'poca', 'pocos', 'pocas', 'bastante', 'demasiado', 'demasiada', 'demasiados',
    'demasiadas', 'hombre', 'mujer', 'nino', 'nina', 'ninos', 'ninas'
}

GERMAN_WORDS = {
    'uber', 'und', 'der', 'die', 'das', 'von', 'mit', 'fur', 'auf', 'bei', 'aus',
    'den', 'ein', 'auch', 'nicht', 'werden', 'haben', 'sein', 'konnen', 'mussen',
    'wollen', 'sollen', 'mogen', 'durch', 'wird', 'kann', 'muss', 'will', 'soll',
    'mag', 'nach', 'uber', 'wurde', 'geworden', 'hatte', 'hatten', 'waren', 'war',
    'ist', 'sind', 'worden', 'werde', 'habe', 'haben', 'hast', 'hat', 'ihr', 'euer',
    'eure', 'mein', 'dein', 'sein', 'ihr', 'unser', 'meine', 'deine', 'seine', 'ihre',
    'unsere', 'meinem', 'deinem', 'seinem', 'ihrem', 'unserem', 'meinen', 'deinen',
    'seinen', 'ihren', 'unseren', 'meiner', 'deiner', 'seiner', 'ihrer', 'unserer',
    'meines', 'deines', 'seines', 'ihres', 'unseres', 'jener', 'jene', 'jenes', 'jenem',
    'jenen', 'jener', 'welcher', 'welche', 'welches', 'welchem', 'welchen', 'welcher',
    'dieser', 'diese', 'dieses', 'diesem', 'diesen', 'dieser', 'mancher', 'manche',
    'manches', 'manchem', 'manchen', 'mancher', 'aller', 'alle', 'alles', 'allen',
    'aller', 'beide', 'beiden', 'beider', 'einige', 'einig', 'einige', 'einigem',
    'einigen', 'einiger', 'mehrere', 'mehrerem', 'mehreren', 'mehrerer', 'vieler',
    'viele', 'vieles', 'vielen', 'vieler', 'etwas', 'nichts', 'wenig', 'wenige',
    'weniges', 'wenigem', 'wenigen', 'weniger', 'genug', 'kein', 'keine', 'keinem',
    'keinen', 'keiner', 'keines', 'jemand', 'niemand', 'einer', 'eines', 'einem',
    'einen', 'einer', 'keiner', 'keines', 'keinem', 'keinen', 'keiner', 'er', 'sie',
    'es', 'ich', 'du', 'wir', 'ihr', 'sie', 'mich', 'dich', 'ihn', 'sie', 'es', 'uns',
    'euch', 'sie', 'mir', 'dir', 'ihm', 'ihr', 'ihm', 'uns', 'euch', 'ihnen', 'mein',
    'dein', 'sein', 'ihr', 'sein', 'unser', 'euer', 'ihr', 'mein', 'dein', 'sein'
}

FRENCH_WORDS = {
    'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'aux', 'avec', 'sans', 'pour',
    'dans', 'sur', 'sous', 'entre', 'vers', 'chez', 'par', 'mais', 'ou', 'et', 'donc',
    'or', 'ni', 'car', 'que', 'qui', 'quoi', 'dont', 'lequel', 'auquel', 'duquel',
    'ce', 'cet', 'cette', 'ces', 'mon', 'ton', 'son', 'notre', 'votre', 'leur', 'mes',
    'tes', 'ses', 'nos', 'vos', 'leurs', 'je', 'tu', 'il', 'elle', 'nous', 'vous',
    'ils', 'elles', 'moi', 'toi', 'lui', 'elle', 'nous', 'vous', 'eux', 'elles', 'me',
    'te', 'le', 'la', 'lui', 'nous', 'vous', 'leur', 'les', 'lui', 'leur', 'y', 'en',
    'mien', 'tien', 'sien', 'notre', 'votre', 'leur', 'miens', 'tiens', 'siens',
    'notres', 'votres', 'leurs', 'celui', 'celle', 'ceux', 'celles', 'ci', 'ca',
    'cela', 'tout', 'toute', 'tous', 'toutes', 'aucun', 'aucune', 'aucuns', 'aucunes',
    'certain', 'certaine', 'certains', 'certaines', 'plusieurs', 'chaque', 'meme',
    'memes', 'autre', 'autres', 'tel', 'telle', 'tels', 'telles', 'quel', 'quelle',
    'quels', 'quelles', 'quelqu\'un', 'quelque', 'quelques', 'rien', 'personne',
    'grand', 'grande', 'grands', 'grandes', 'petit', 'petite', 'petits', 'petites',
    'bon', 'bonne', 'bons', 'bonnes', 'mauvais', 'mauvaise', 'mauvais', 'mauvaises',
    'beau', 'belle', 'beaux', 'belles', 'jeune', 'jeunes', 'vieux', 'vieille', 'vieux',
    'vieilles', 'nouveau', 'nouvelle', 'nouveaux', 'nouvelles', 'homme', 'femme',
    'enfant', 'enfants', 'garcon', 'fille'
}

ITALIAN_WORDS = {
    'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una', 'dei', 'degli', 'delle',
    'del', 'della', 'dello', 'a', 'da', 'di', 'in', 'con', 'su', 'per', 'tra', 'fra',
    'verso', 'contro', 'senza', 'oltre', 'presso', 'secondo', 'durante', 'mediante',
    'non', 'si', 'piu', 'solo', 'anche', 'ancora', 'gia', 'sempre', 'mai', 'tuttora',
    'oppure', 'ed', 'e', 'ne', 'che', 'chi', 'cui', 'quale', 'quali', 'quello',
    'quella', 'quelli', 'quelle', 'questo', 'questa', 'questi', 'queste', 'cio', 'codesto',
    'tale', 'tali', 'tutto', 'tutta', 'tutti', 'tutte', 'nessun', 'nessuna', 'nessuni',
    'nessune', 'alcun', 'alcuna', 'alcuni', 'alcune', 'qualche', 'qualcuna', 'certo',
    'certa', 'certi', 'certe', 'molto', 'molta', 'molti', 'molte', 'poco', 'poca',
    'pochi', 'poco', 'troppo', 'troppa', 'troppi', 'troppe', 'parecchio', 'parecchia',
    'parecchi', 'parecchie', 'alquanto', 'basta', 'abbastanza', 'mio', 'mia', 'miei',
    'mie', 'tuo', 'tua', 'tuoi', 'tue', 'suo', 'sua', 'suoi', 'sue', 'nostro', 'nostra',
    'nostri', 'nostre', 'vostro', 'vostra', 'vostri', 'vostre', 'loro', 'io', 'tu',
    'lui', 'lei', 'noi', 'voi', 'loro', 'me', 'te', 'lo', 'la', 'ci', 'vi', 'li', 'le',
    'ne', 'essi', 'esse', 'esso', 'essa', 'essi', 'esse', 'sé', 'proprio', 'propria',
    'proprio', 'propri', 'proprie', 'stesso', 'stessa', 'stessi', 'stesse', 'altri',
    'altre', 'altra', 'qualcuno', 'qualcuna', 'nessuno', 'nessuna', 'niente', 'nulla',
    'ogni', 'qualunque', 'qualsiasi', 'ciascuno', 'ciascuna', 'uomo', 'donna', 'bambino',
    'bambina', 'bambini', 'bambine', 'ragazzo', 'ragazza'
}

PORTUGUESE_WORDS = {
    'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'de', 'do', 'da', 'dos', 'das',
    'em', 'no', 'na', 'nos', 'nas', 'por', 'para', 'com', 'sem', 'sobre', 'sob', 'entre',
    'mas', 'ou', 'nem', 'que', 'quem', 'cujo', 'cuja', 'cujos', 'cujas', 'este', 'esta',
    'isto', 'estes', 'estas', 'esse', 'essa', 'isso', 'esses', 'essas', 'aquele', 'aquela',
    'aquilo', 'aqueles', 'aquelas', 'isto', 'aquilo', 'outro', 'outra', 'outros', 'outras',
    'todo', 'toda', 'todos', 'todas', 'algum', 'alguma', 'alguns', 'algumas', 'nenhum',
    'nenhuma', 'nenhuns', 'nenhumas', 'muito', 'muita', 'muitos', 'muitas', 'pouco',
    'pouca', 'poucos', 'poucas', 'tanto', 'tanta', 'tantos', 'tantas', 'meu', 'minha',
    'meus', 'minhas', 'teu', 'tua', 'teus', 'tuas', 'seu', 'sua', 'seus', 'suas', 'nosso',
    'nossa', 'nossos', 'nossas', 'vosso', 'vossa', 'vossos', 'vossas', 'lhe', 'lhes', 'me',
    'te', 'nos', 'vos', 'o', 'a', 'lhes', 'lhe', 'o', 'a', 'lo', 'la', 'los', 'las', 'si',
    'conosco', 'contigo', 'consigo', 'conosco', 'convosco', 'eu', 'tu', 'ele', 'ela', 'nos',
    'vos', 'eles', 'elas', 'mim', 'ti', 'ele', 'ela', 'nos', 'vos', 'eles', 'elas', 'quem',
    'algo', 'nada', 'tudo', 'alguem', 'ninguem', 'cada', 'proprio', 'propria', 'proprios',
    'proprias', 'mesmo', 'mesma', 'mesmos', 'mesmas', 'so', 'só', 'tambem', 'ainda', 'ja',
    'ja', 'nao', 'nao', 'sim', 'homem', 'mulher', 'crianca', 'criancas', 'rapaz', 'rapariga'
}

RUSSIAN_WORDS = {
    'da', 'nie', 'pasaran', 'tovarisch', 'su', 'dov', 'ak', 'privet', 'poka', 'spasibo',
    'pozhaluista', 'net', 'mozhno', 'nelzya', 'please', 'thank', 'you', 'hello', 'goodbye',
    'da', 'net', 'mozhno', 'nelzya', 'please', 'thank', 'you', 'hello', 'goodbye'
}

DUTCH_WORDS = {
    'de', 'het', 'een', 'van', 'der', 'in', 'op', 'aan', 'met', 'voor', 'bij', 'naar',
    'uit', 'over', 'door', 'tegen', 'zonder', 'onder', 'boven', 'beneden', 'tussen',
    'langs', 'achter', 'via', 'per', 'gedurende', 'tijdens', 'na', 'voordat', 'toen',
    'als', 'zodat', 'omdat', 'doordat', 'aangezien', 'hoewel', 'ofschoon', 'alhoewel',
    'indien', 'tenzij', 'of', 'doch', 'maar', 'echter', 'toch', 'desondanks', 'desalniettemin',
    'en', 'zowel', 'doch', 'noch', 'of', 'of', 'zowel', 'als', 'dat', 'wat', 'wie',
    'welke', 'welk', 'deze', 'dit', 'die', 'dat', 'deze', 'die', 'het', 'hem', 'haar',
    'het', 'hen', 'hun', 'zij', 'mij', 'jou', 'u', 'ons', 'jullie', 'mijn', 'jouw',
    'uw', 'zijn', 'haar', 'ons', 'jullie', 'hun', 'mijne', 'jouwe', 'uwe', 'zijne',
    'hare', 'onze', 'van', 'ons', 'jullie', 'hun', 'de', 'een', 'geen', 'enkele',
    'enzige', 'eene', 'vel', 'weinig', 'veel', 'meest', 'meeste', 'al', 'alle',
    'beide', 'elk', 'elke', 'ieder', 'iedere', 'menig', 'menige', 'zulk', 'zulke',
    'geen', 'geen', 'niemand', 'niets', 'iets', 'alles', 'iedereen', 'iederieder',
    'dezelfde', 'dezelfde', 'zelfde', 'zelfde', 'de', 'man', 'vrouw', 'kind'
}

SWEDISH_WORDS = {
    'en', 'ett', 'den', 'det', 'de', 'av', 'fran', 'ur', 'till', 'for', 'med', 'utan',
    'pa', 'over', 'under', 'om', 'genom', 'vid', 'hos', 'framfor', 'bakom', 'bredvid',
    'sidan', 'efter', 'under', 'darfor', 'dav', 'der', 'darefter', 'fore', 'innan', 'nad',
    'da', 'd', 'eftersom', 'eftersom', 'om', 'att', 'om', 'att', 'd', 'om', 'att', 'om',
    'att', 'om', 'att', 'om', 'att', 'eller', 'men', 'dock', 'lika', 'vel', 'som',
    'att', 'som', 'vilken', 'vilket', 'vilka', 'vilken', 'vilket', 'vilka', 'den', 'det',
    'de', 'den', 'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de',
    'den', 'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de', 'den',
    'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de', 'min', 'din',
    'sin', 'vart', 'var', 'ert', 'er', 'vart', 'var', 'ert', 'er', 'vart', 'var', 'ert',
    'er', 'vart', 'var', 'ert', 'er', 'vart', 'var', 'ert', 'er', 'vart', 'var', 'ert',
    'er', 'den', 'som', 'vilken', 'vilket', 'vilka', 'nagon', 'nagot', 'nagra', 'ingen',
    'inget', 'inga', 'alla', 'bada', 'bada', 'varje', 'varje', 'varje', 'varje', 'ingen',
    'inget', 'inga', 'man', 'en', 'ett', 'nagon', 'nagot', 'nagra', 'ingen', 'inget',
    'inga', 'alla', 'ingen', 'inget', 'inga', 'all', 'man', 'kvinna', 'barn'
}

NORWEGIAN_WORDS = {
    'en', 'ei', 'et', 'den', 'det', 'de', 'av', 'fra', 'til', 'for', 'med', 'uten',
    'pa', 'over', 'under', 'om', 'gjennom', 'ved', 'foran', 'bak', 'siden', 'etter',
    'for', 'derfor', 'derav', 'der', 'etterp', 'etter', 'for', 'inn', 'inne', 'ut',
    'ute', 'opp', 'ned', 'inn', 'over', 'rundt', 'gjennom', 'tvers', 'forbi', 'gjennom',
    'da', 'fordi', 'ettersom', 'eftersom', 'at', 'for', 'at', 'om', 'att', 'eller',
    'men', 'dog', 'likevel', 'allikevel', 'som', 'at', 'som', 'hvilken', 'hvilket',
    'hvilke', 'hvem', 'hva', 'hvilken', 'hvilket', 'hvilke', 'hvem', 'hva', 'den',
    'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de', 'den',
    'det', 'de', 'den', 'det', 'de', 'den', 'det', 'de', 'min', 'din', 'sin', 'vart',
    'var', 'vart', 'var', 'ert', 'er', 'vart', 'var', 'ert', 'er', 'vart', 'var',
    'ert', 'er', 'den', 'som', 'hvilken', 'hvilket', 'hvilke', 'nogen', 'noe', 'noen',
    'ingen', 'ingenting', 'ingen', 'ingen', 'ingenting', 'ingen', 'ingen', 'ingenting',
    'ingen', 'alle', 'begge', 'begge', 'hver', 'hvert', 'hver', 'hver', 'hvert', 'hver',
    'ingen', 'ingenting', 'ingen', 'ingen', 'ingenting', 'ingen', 'ingen', 'ingenting',
    'ingen', 'ingen', 'ingenting', 'ingen', 'ingen', 'ingenting', 'ingen', 'mann',
    'kvinne', 'barn'
}

# Common city names to reject (geographic terms)
GEOGRAPHIC_NAMES = {
    'london', 'paris', 'tokyo', 'berlin', 'madrid', 'rome', 'moscow', 'beijing', 'shanghai',
    'delhi', 'mumbai', 'sydney', 'toronto', 'dubai', 'singapore', 'amsterdam', 'barcelona',
    'vienna', 'prague', 'budapest', 'warsaw', 'athens', 'lisbon', 'dublin', 'brussels',
    'copenhagen', 'stockholm', 'oslo', 'helsinki', 'reykjavik', 'zurich', 'geneva',
    'milan', 'venice', 'florence', 'naples', 'seattle', 'portland', 'austin', 'denver',
    'nashville', 'chicago', 'boston', 'phoenix', 'dallas', 'houston', 'atlanta', 'miami',
    'san', 'los', 'las', 'new', 'york', 'jersey', 'francisco', 'diego', 'jose',
}

# Combined non-English words set
NON_ENGLISH_WORDS = (SPANISH_WORDS | GERMAN_WORDS | FRENCH_WORDS | ITALIAN_WORDS |
                     PORTUGUESE_WORDS | RUSSIAN_WORDS | DUTCH_WORDS | SWEDISH_WORDS |
                     NORWEGIAN_WORDS)

# Functional SaaS verbs - directly describe function (expanded)
FUNCTIONAL_VERBS = {
    'sync', 'merge', 'deploy', 'track', 'build', 'parse', 'render', 'queue', 'route',
    'stream', 'connect', 'link', 'bridge', 'bind', 'join', 'split', 'slice', 'map',
    'reduce', 'filter', 'sort', 'search', 'find', 'match', 'replace', 'transform',
    'convert', 'translate', 'encode', 'decode', 'encrypt', 'decrypt', 'compress',
    'extract', 'archive', 'backup', 'restore', 'clone', 'copy', 'paste',
    'move', 'transfer', 'upload', 'download', 'share', 'send', 'receive', 'fetch',
    'push', 'pull', 'commit', 'publish', 'subscribe', 'notify', 'alert', 'monitor',
    'log', 'debug', 'test', 'verify', 'validate', 'check', 'scan', 'analyze',
    'compute', 'calculate', 'process', 'execute', 'run', 'schedule', 'trigger',
    'automate', 'orchestrate', 'coordinate', 'manage', 'organize', 'index',
    'aggregate', 'disseminate', 'retrieve', 'store', 'host', 'serve', 'deliver',
    # Additional functional words
    'integrate', 'compose', 'assemble', 'construct', 'compile', 'generate', 'produce',
    'dispatch', 'distribute', 'broadcast', 'transmit', 'propagate', 'replicate',
    'synchronize', 'align', 'balance', 'equalize', 'normalize', 'standardize',
    'optimize', 'improve', 'enhance', 'refine', 'polish', 'perfect', 'complete',
    'initiate', 'launch', 'start', 'begin', 'activate', 'enable', 'disable', 'stop',
    'pause', 'resume', 'continue', 'proceed', 'advance', 'progress', 'evolve',
    'capture', 'collect', 'gather', 'accumulate', 'amass', 'harvest', 'acquire',
    'preserve', 'protect', 'secure', 'guard', 'defend', 'shield', 'screen', 'block',
    # Common SaaS functional words
    'mark', 'point', 'flag', 'tag', 'label', 'note', 'annotate', 'comment', 'review',
    'approve', 'reject', 'accept', 'decline', 'confirm', 'cancel', 'delete', 'remove',
    'create', 'make', 'add', 'insert', 'update', 'edit', 'modify', 'change', 'alter',
    'save', 'submit', 'post', 'get', 'load', 'refresh', 'reload', 'reset', 'clear',
    'export', 'import', 'format', 'view', 'show', 'hide', 'display', 'print', 'download',
    'sign', 'login', 'logout', 'register', 'signup', 'auth', 'authenticate', 'authorize'
}

# Brandable words - suitable for product/brand names (expanded)
BRANDABLE_WORDS = {
    'forge', 'pulse', 'nexus', 'apex', 'orbit', 'nova', 'beacon', 'vault', 'spark',
    'craft', 'flow', 'core', 'stack', 'mesh', 'grid', 'hub', 'edge', 'node', 'peak',
    'summit', 'zenith', 'vertex', 'cascade', 'flux', 'drift', 'wave', 'tide', 'current',
    'signal', 'path', 'lane', 'route', 'way', 'bridge', 'link', 'chain', 'loop',
    'ring', 'circle', 'sphere', 'domain', 'realm', 'zone', 'area', 'field', 'scope',
    'range', 'reach', 'span', 'beam', 'ray', 'gleam', 'glow', 'shine', 'bright',
    'lumin', 'terra', 'astra', 'cosmo', 'stellar', 'solar', 'lunar', 'meteor',
    'comet', 'quasar', 'pulsar', 'nebula', 'galaxy', 'horizon', 'meridian',
    # Additional brandable words
    'pivot', 'anchor', 'base', 'camp', 'dock', 'port', 'terminal', 'gateway', 'portal',
    'gate', 'door', 'key', 'lock', 'vault', 'safe', 'keeper', 'guard', 'warden',
    'shield', 'armor', 'helmet', 'mask', 'cloak', 'veil', 'cover', 'lid', 'cap',
    'crown', 'crest', 'helm', 'throne', 'seat', 'stand', 'stage', 'platform', 'deck',
    'tower', 'spire', 'peak', 'cliff', 'ridge', 'valley', 'canyon', 'gorge', 'rift',
    'stream', 'river', 'brook', 'creek', 'spring', 'well', 'fountain', 'source',
    'origin', 'root', 'seed', 'core', 'heart', 'center', 'midst', 'nucleus', 'kernel',
    'spark', 'flash', 'flare', 'blaze', 'flame', 'fire', 'burn', 'glow', 'shine',
    'light', 'ray', 'beam', 'glare', 'glimmer', 'glint', 'twinkle', 'radiant',
    'shadow', 'shade', 'dark', 'dim', 'gloom', 'dusk', 'dawn', 'twilight', 'eve'
}

# Brandable words - suitable for product/brand names
BRANDABLE_WORDS = {
    'forge', 'pulse', 'nexus', 'apex', 'orbit', 'nova', 'beacon', 'vault', 'spark',
    'craft', 'flow', 'core', 'stack', 'mesh', 'grid', 'hub', 'edge', 'node', 'peak',
    'summit', 'zenith', 'vertex', 'cascade', 'flux', 'drift', 'wave', 'tide', 'current',
    'signal', 'path', 'lane', 'route', 'way', 'bridge', 'link', 'chain', 'loop',
    'ring', 'circle', 'sphere', 'domain', 'realm', 'zone', 'area', 'field', 'scope',
    'range', 'reach', 'span', 'beam', 'ray', 'gleam', 'glow', 'shine', 'bright',
    'lumin', 'terra', 'astra', 'cosmo', 'stellar', 'solar', 'lunar', 'meteor',
    'comet', 'quasar', 'pulsar', 'nebula', 'galaxy', 'horizon', 'meridian',
}

def has_repeated_chars(word: str, threshold: int = 3) -> bool:
    """Check if word has 3+ consecutive repeated characters"""
    if len(word) < threshold:
        return False
    for i in range(len(word) - threshold + 1):
        if len(set(word[i:i+threshold])) == 1:
            return True
    return False

def is_pure_noise(word: str) -> bool:
    """Check if word is pure symbol/string"""
    # No letters at all
    if not re.search(r'[a-zA-Z]', word):
        return True
    # Dominated by special chars
    alpha_count = sum(1 for c in word if c.isalpha())
    if len(word) > 0 and alpha_count / len(word) < 0.3:
        return True
    return False

def judge_01_recall_focused(word: str) -> Dict[str, Any]:
    """Judge 01: Most lenient, focuses on recall - ACCEPT if ANY doubt"""
    word_lower = word.lower()
    clean_word = ''.join(c for c in word_lower if c.isalpha())

    # Only reject absolute garbage
    if is_pure_noise(word):
        return {"decision": "reject", "label": None, "confidence": 0.95,
                "why": ["pure noise - no letters", "or insufficient letter ratio"]}

    if has_repeated_chars(word, 3):
        return {"decision": "reject", "label": None, "confidence": 0.9,
                "why": ["3+ consecutive repeated chars", "visual clutter"]}

    # URL/path fragments
    if re.match(r'^(https?|www|\.|\w+\.\w+|/[\w/]+)', word_lower):
        return {"decision": "reject", "label": None, "confidence": 0.9,
                "why": ["URL or path fragment", "not standalone word"]}

    # Code tokens
    if re.match(r'^__.*__$', word) or re.match(r'^0x[0-9A-Fa-f]+$', word):
        return {"decision": "reject", "label": None, "confidence": 0.95,
                "why": ["code token", "programming syntax"]}

    # Check for functional patterns (verbs ending in common SaaS suffixes)
    functional_suffixes = ['sync', 'merge', 'deploy', 'track', 'build', 'parse', 'render',
                          'queue', 'route', 'stream', 'connect', 'link', 'bridge', 'bind',
                          'join', 'split', 'slice', 'map', 'reduce', 'filter', 'sort',
                          'search', 'find', 'match', 'replace', 'transform', 'convert',
                          'translate', 'encode', 'decode', 'encrypt', 'decrypt', 'compress',
                          'extract', 'archive', 'backup', 'restore', 'clone', 'copy', 'paste',
                          'move', 'transfer', 'upload', 'download', 'share', 'send', 'receive',
                          'fetch', 'push', 'pull', 'commit', 'publish', 'subscribe', 'notify',
                          'alert', 'monitor', 'log', 'debug', 'test', 'verify', 'validate',
                          'check', 'scan', 'analyze', 'compute', 'calculate', 'process',
                          'execute', 'run', 'schedule', 'trigger', 'automate', 'orchestrate',
                          'coordinate', 'manage', 'organize', 'index', 'aggregate',
                          'disseminate', 'retrieve', 'store', 'host', 'serve', 'deliver',
                          'integrate', 'compose', 'assemble', 'construct', 'compile',
                          'generate', 'produce', 'dispatch', 'distribute', 'broadcast',
                          'transmit', 'propagate', 'replicate', 'synchronize', 'align',
                          'balance', 'equalize', 'normalize', 'standardize', 'optimize',
                          'improve', 'enhance', 'refine', 'polish', 'perfect', 'complete',
                          'initiate', 'launch', 'start', 'begin', 'activate', 'enable',
                          'disable', 'stop', 'pause', 'resume', 'continue', 'proceed',
                          'advance', 'progress', 'evolve', 'capture', 'collect', 'gather',
                          'accumulate', 'amass', 'harvest', 'acquire', 'preserve', 'protect',
                          'secure', 'guard', 'defend', 'shield', 'screen', 'block']

    # Check brandable patterns (abstract nouns, evocative words)
    brandable_patterns = ['forge', 'pulse', 'nexus', 'apex', 'orbit', 'nova', 'beacon',
                          'vault', 'spark', 'craft', 'flow', 'core', 'stack', 'mesh', 'grid',
                          'hub', 'edge', 'node', 'peak', 'summit', 'zenith', 'vertex',
                          'cascade', 'flux', 'drift', 'wave', 'tide', 'current', 'signal',
                          'path', 'lane', 'route', 'way', 'bridge', 'link', 'chain', 'loop',
                          'ring', 'circle', 'sphere', 'domain', 'realm', 'zone', 'area',
                          'field', 'scope', 'range', 'reach', 'span', 'beam', 'ray', 'gleam',
                          'glow', 'shine', 'bright', 'lumin', 'terra', 'astra', 'cosmo',
                          'stellar', 'solar', 'lunar', 'meteor', 'comet', 'quasar', 'pulsar',
                          'nebula', 'galaxy', 'horizon', 'meridian', 'pivot', 'anchor',
                          'base', 'camp', 'dock', 'port', 'terminal', 'gateway', 'portal',
                          'gate', 'door', 'key', 'lock', 'keeper', 'guard', 'warden',
                          'shield', 'armor', 'helmet', 'mask', 'cloak', 'veil', 'cover',
                          'crown', 'crest', 'helm', 'throne', 'seat', 'stand', 'stage',
                          'platform', 'deck', 'tower', 'spire', 'cliff', 'ridge', 'valley',
                          'canyon', 'gorge', 'rift', 'river', 'brook', 'creek', 'spring',
                          'well', 'fountain', 'source', 'origin', 'root', 'seed', 'heart',
                          'center', 'midst', 'nucleus', 'kernel', 'flash', 'flare', 'blaze',
                          'flame', 'fire', 'burn', 'light', 'shadow', 'shade', 'dark',
                          'dusk', 'dawn', 'twilight', 'eve']

    # Determine label based on patterns
    clean_lower = clean_word.lower()
    if clean_lower in functional_suffixes:
        return {"decision": "accept", "label": "functional", "confidence": 0.85,
                "why": ["recall priority", "functional pattern detected"]}
    elif clean_lower in brandable_patterns:
        return {"decision": "accept", "label": "brandable", "confidence": 0.85,
                "why": ["recall priority", "brandable pattern detected"]}
    else:
        return {"decision": "accept", "label": "ambiguous", "confidence": 0.7,
                "why": ["recall priority", "benefit of doubt given"]}

def judge_02_brand_focused(word: str) -> Dict[str, Any]:
    """Judge 02: Brand value focused - rejects generic, seeks evocative"""
    word_lower = word.lower()
    clean_word = ''.join(c for c in word_lower if c.isalpha())

    if is_pure_noise(word):
        return {"decision": "reject", "label": None, "confidence": 0.98,
                "why": ["no brand value", "incoherent"]}

    if has_repeated_chars(word, 3):
        return {"decision": "reject", "label": None, "confidence": 0.95,
                "why": ["repetitive - unprofessional", "brand liability"]}

    # Explicit rejections
    if word_lower in GENERIC_WORDS_ADDITIONAL:
        return {"decision": "reject", "label": None, "confidence": 0.95,
                "why": ["generic grammatical word", "zero brand differentiation"]}

    if clean_word in NON_ENGLISH_WORDS:
        return {"decision": "reject", "label": None, "confidence": 0.96,
                "why": ["non-English word", "not suitable for English SaaS branding"]}

    if word_lower in GEOGRAPHIC_NAMES:
        return {"decision": "reject", "label": None, "confidence": 0.92,
                "why": ["geographic name", "trademark restrictions"]}

    # Strong brandable words
    if clean_word in BRANDABLE_WORDS:
        return {"decision": "accept", "label": "brandable", "confidence": 0.95,
                "why": ["evocative imagery", "strong brand potential", "memorable"]}

    # Check for startup-style suffixes
    if re.search(r'(ly|ify|io|hq|lab|stack|flow|hub)\s*$', word_lower):
        return {"decision": "accept", "label": "brandable", "confidence": 0.85,
                "why": ["startup-style branding", "tech-savvy suffix"]}

    # Abstract nouns work well as brands
    abstract_nouns = {'flow', 'core', 'stack', 'mesh', 'grid', 'bridge', 'hub', 'link', 'edge', 'node'}
    if clean_word in abstract_nouns:
        return {"decision": "accept", "label": "brandable", "confidence": 0.9,
                "why": ["abstract concept", "metaphorical brand value"]}

    # Default: cautious accept
    if word.isalpha() and len(word) >= 3:
        return {"decision": "accept", "label": "ambiguous", "confidence": 0.6,
            "why": ["plausible but unproven", "needs context"]}

    return {"decision": "reject", "label": None, "confidence": 0.7,
            "why": ["insufficient brand clarity"]}

def judge_03_technical_focused(word: str) -> Dict[str, Any]:
    """Judge 03: Technical/functional value focused"""
    word_lower = word.lower()
    clean_word = ''.join(c for c in word_lower if c.isalpha())

    if is_pure_noise(word):
        return {"decision": "reject", "label": None, "confidence": 0.98,
                "why": ["no technical meaning"]}

    if has_repeated_chars(word, 3):
        return {"decision": "reject", "label": None, "confidence": 0.92,
                "why": ["pattern looks like noise", "not technical term"]}

    # Functional verbs are gold
    if clean_word in FUNCTIONAL_VERBS:
        return {"decision": "accept", "label": "functional", "confidence": 0.97,
                "why": ["clear SaaS functionality", "action-oriented", "domain-relevant"]}

    # Generic words have no technical value
    if word_lower in GENERIC_WORDS_ADDITIONAL:
        return {"decision": "reject", "label": None, "confidence": 0.93,
                "why": ["no technical specificity", "too generic for tech product"]}

    if clean_word in NON_ENGLISH_WORDS:
        return {"decision": "reject", "label": None, "confidence": 0.94,
                "why": ["non-English technical term", "not suitable for English SaaS"]}

    # Tech-sounding patterns
    tech_suffixes = ['sync', 'cast', 'share', 'base', 'cloud', 'data', 'code', 'ware', 'soft', 'sys']
    if any(word_lower.endswith(s) for s in tech_suffixes):
        return {"decision": "accept", "label": "functional", "confidence": 0.8,
                "why": ["technical suffix pattern", "domain-relevant"]}

    # Check for tech prefix patterns
    tech_prefixes = ['auto', 'multi', 'inter', 'intra', 'trans', 'meta', 'hyper', 'super']
    if any(word_lower.startswith(p) for p in tech_prefixes):
        return {"decision": "accept", "label": "functional", "confidence": 0.75,
                "why": ["technical prefix", "systemic implication"]}

    # Abstract tech concepts
    tech_concepts = {'queue', 'stream', 'buffer', 'cache', 'proxy', 'gateway', 'router', 'switch'}
    if clean_word in tech_concepts:
        return {"decision": "accept", "label": "functional", "confidence": 0.9,
                "why": ["technical concept", "computing relevance"]}

    # Plausible tech word
    if word.isalpha() and len(word) >= 4:
        return {"decision": "accept", "label": "ambiguous", "confidence": 0.65,
                "why": ["possible technical term", "needs domain verification"]}

    return {"decision": "reject", "label": None, "confidence": 0.75,
            "why": ["unclear technical value"]}

def judge_04_english_word_focused(word: str) -> Dict[str, Any]:
    """Judge 04: Real English word verification - strict but fair"""
    word_lower = word.lower()
    clean_word = ''.join(c for c in word_lower if c.isalpha())

    # Pure rejection: not English
    if is_pure_noise(word):
        return {"decision": "reject", "label": None, "confidence": 0.99,
                "why": ["not English word", "no alphabetic content"]}

    if has_repeated_chars(word, 3):
        return {"decision": "reject", "label": None, "confidence": 0.93,
                "why": ["non-standard English pattern", "excessive repetition"]}

    # Contains numbers or symbols - not pure English
    if not word.isalpha():
        return {"decision": "reject", "label": None, "confidence": 0.9,
                "why": ["contains non-letters", "not pure English word"]}

    # Check if non-English word
    if clean_word in NON_ENGLISH_WORDS:
        return {"decision": "reject", "label": None, "confidence": 0.97,
                "why": ["verified non-English word", "not suitable for English SaaS"]}

    # Generic English words - still English but too common
    if word_lower in GENERIC_WORDS_ADDITIONAL:
        return {"decision": "reject", "label": None, "confidence": 0.9,
                "why": ["valid English but too generic", "low specificity for product naming"]}

    # Geographic names are English but not usable
    if word_lower in GEOGRAPHIC_NAMES:
        return {"decision": "reject", "label": None, "confidence": 0.88,
                "why": ["English place name", "geographic restriction"]}

    # Valid English word structure
    if len(word) >= 3 and word.isalpha():
        # Vowel check - English words need vowels
        has_vowel = any(c in 'aeiouy' for c in word_lower)
        if has_vowel:
            # Check for verb patterns (functional)
            verb_endings = ['ate', 'ify', 'ize', 'ise', 'en', 'er', 'or', 'sync', 'cast',
                           'share', 'base', 'cloud', 'data', 'code', 'ware', 'soft', 'sys']
            if any(word_lower.endswith(e) for e in verb_endings):
                return {"decision": "accept", "label": "functional", "confidence": 0.75,
                        "why": ["valid English word", "verb pattern detected"]}
            # Check for noun patterns (brandable)
            noun_endings = ['er', 'or', 'ment', 'ness', 'ity', 'tion', 'sion', 'ance',
                           'ence', 'dom', 'ship', 'hood', 'ware', 'ware', 'gate', 'hub',
                           'port', 'dock', 'yard', 'field', 'park', 'land', 'scape']
            if any(word_lower.endswith(e) for e in noun_endings):
                return {"decision": "accept", "label": "brandable", "confidence": 0.7,
                        "why": ["valid English word", "noun pattern detected"]}
            return {"decision": "accept", "label": "ambiguous", "confidence": 0.8,
                    "why": ["valid English word structure", "contains vowel", "plausible"]}
        # Short words without vowels might still be English (by, my, sky, etc)
        if len(word) <= 3:
            return {"decision": "accept", "label": "ambiguous", "confidence": 0.6,
                    "why": ["short word exception", "possible abbreviation"]}

    return {"decision": "reject", "label": None, "confidence": 0.7,
            "why": ["invalid English structure"]}

def judge_05_balanced(word: str) -> Dict[str, Any]:
    """Judge 05: Balanced quality review - practical SaaS perspective"""
    word_lower = word.lower()
    clean_word = ''.join(c for c in word_lower if c.isalpha())

    # Hard rejections
    if is_pure_noise(word):
        return {"decision": "reject", "label": None, "confidence": 0.98,
                "why": ["no discernible value", "incoherent"]}

    if has_repeated_chars(word, 3):
        return {"decision": "reject", "label": None, "confidence": 0.93,
                "why": ["unprofessional appearance", "visual noise"]}

    # URL/path fragments
    if re.match(r'^(https?|www|\.|\w+\.\w+|/[\w/]+)', word_lower):
        return {"decision": "reject", "label": None, "confidence": 0.92,
                "why": ["system artifact", "not standalone word"]}

    # Code tokens
    if re.match(r'^__.*__$', word) or re.match(r'^0x[0-9A-Fa-f]+$', word):
        return {"decision": "reject", "label": None, "confidence": 0.96,
                "why": ["programming artifact", "not product name"]}

    # Generic words - no value
    if word_lower in GENERIC_WORDS_ADDITIONAL:
        return {"decision": "reject", "label": None, "confidence": 0.94,
                "why": ["zero differentiation", "too common", "marketing liability"]}

    # Non-English words
    if clean_word in NON_ENGLISH_WORDS:
        return {"decision": "reject", "label": None, "confidence": 0.95,
                "why": ["non-English word", "not suitable for English SaaS market"]}

    # Geographic - trademark risk
    if word_lower in GEOGRAPHIC_NAMES:
        return {"decision": "reject", "label": None, "confidence": 0.9,
                "why": ["trademark risk", "geographic limitation"]}

    # Strong accepts
    if clean_word in FUNCTIONAL_VERBS:
        return {"decision": "accept", "label": "functional", "confidence": 0.95,
                "why": ["clear functional value", "user understands purpose"]}

    if clean_word in BRANDABLE_WORDS:
        return {"decision": "accept", "label": "brandable", "confidence": 0.95,
                "why": ["evocative and memorable", "branding potential"]}

    # Check for patterns to assign labels more intelligently
    # Action verbs = functional
    action_endings = ['ate', 'ify', 'ize', 'ise', 'en', 'sync', 'cast', 'share', 'base',
                     'cloud', 'data', 'code', 'ware', 'soft', 'sys', 'track', 'build',
                     'parse', 'render', 'queue', 'route', 'stream', 'connect', 'link',
                     'bridge', 'bind', 'join', 'split', 'slice', 'map', 'reduce',
                     'filter', 'sort', 'search', 'find', 'match', 'replace', 'transform',
                     'convert', 'translate', 'encode', 'decode', 'encrypt', 'decrypt',
                     'compress', 'extract', 'archive', 'backup', 'restore', 'clone',
                     'copy', 'paste', 'move', 'transfer', 'upload', 'download', 'share',
                     'send', 'receive', 'fetch', 'push', 'pull', 'commit', 'publish',
                     'subscribe', 'notify', 'alert', 'monitor', 'log', 'debug', 'test',
                     'verify', 'validate', 'check', 'scan', 'analyze', 'compute',
                     'calculate', 'process', 'execute', 'run', 'schedule', 'trigger',
                     'automate', 'orchestrate', 'coordinate', 'manage', 'organize',
                     'index', 'aggregate', 'disseminate', 'retrieve', 'store', 'host',
                     'serve', 'deliver', 'integrate', 'compose', 'assemble', 'construct',
                     'compile', 'generate', 'produce', 'dispatch', 'distribute',
                     'broadcast', 'transmit', 'propagate', 'replicate', 'synchronize',
                     'align', 'balance', 'equalize', 'normalize', 'standardize',
                     'optimize', 'improve', 'enhance', 'refine', 'polish', 'perfect',
                     'complete', 'initiate', 'launch', 'start', 'begin', 'activate',
                     'enable', 'disable', 'stop', 'pause', 'resume', 'continue',
                     'proceed', 'advance', 'progress', 'evolve', 'capture', 'collect',
                     'gather', 'accumulate', 'amass', 'harvest', 'acquire', 'preserve',
                     'protect', 'secure', 'guard', 'defend', 'shield', 'screen', 'block']
    if any(word_lower.endswith(e) for e in action_endings):
        return {"decision": "accept", "label": "functional", "confidence": 0.8,
                "why": ["action-oriented word", "functional intent", "usable"]}

    # Nouns/abstract concepts = brandable
    noun_endings = ['er', 'or', 'ment', 'ness', 'ity', 'tion', 'sion', 'ance', 'ence',
                   'dom', 'ship', 'hood', 'gate', 'hub', 'port', 'dock', 'yard', 'field',
                   'park', 'land', 'scape', 'ware', 'ware', 'core', 'stack', 'mesh',
                   'grid', 'flow', 'peak', 'summit', 'zenith', 'vertex', 'cascade',
                   'flux', 'drift', 'wave', 'tide', 'current', 'signal', 'path', 'lane',
                   'route', 'way', 'bridge', 'link', 'chain', 'loop', 'ring', 'circle',
                   'sphere', 'domain', 'realm', 'zone', 'area', 'scope', 'range', 'reach',
                   'span', 'beam', 'ray', 'gleam', 'glow', 'shine', 'bright', 'lumin',
                   'terra', 'astra', 'cosmo', 'stellar', 'solar', 'lunar', 'meteor',
                   'comet', 'quasar', 'pulsar', 'nebula', 'galaxy', 'horizon', 'meridian']
    if any(word_lower.endswith(e) for e in noun_endings):
        return {"decision": "accept", "label": "brandable", "confidence": 0.75,
                "why": ["noun-based word", "brandable concept", "evocative"]}

    # Reasonable words get benefit of doubt
    if word.isalpha() and len(word) >= 3 and len(word) <= 12:
        return {"decision": "accept", "label": "ambiguous", "confidence": 0.7,
                "why": ["within reasonable bounds", "usable candidate", "needs context"]}

    return {"decision": "reject", "label": None, "confidence": 0.65,
            "why": ["outside usable parameters"]}

def process_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single record through all 5 judges"""
    word = record.get("normalized_word", "")

    judges = [
        ("saas-title-judge-01", judge_01_recall_focused),
        ("saas-title-judge-02", judge_02_brand_focused),
        ("saas-title-judge-03", judge_03_technical_focused),
        ("saas-title-judge-04", judge_04_english_word_focused),
        ("saas-title-judge-05", judge_05_balanced),
    ]

    votes = []
    accept_count = 0
    reject_count = 0
    borderline_count = 0

    for judge_id, judge_func in judges:
        result = judge_func(word)
        vote = {
            "judge_id": judge_id,
            "decision": result["decision"],
            "label": result["label"],
            "confidence": result["confidence"],
            "why": result["why"]
        }
        votes.append(vote)

        if result["decision"] == "accept":
            accept_count += 1
        elif result["decision"] == "reject":
            reject_count += 1
        else:
            borderline_count += 1

    # Add votes to record
    record["primary_votes"] = votes
    record["primary_summary"] = {
        "accept": accept_count,
        "reject": reject_count,
        "borderline": borderline_count
    }
    record["status"] = "AI_PRIMARY_REVIEWED"

    return record

def main():
    input_path = Path("output/intermediate/04_screened_tokens.jsonl")
    output_path = Path("output/intermediate/05_primary_reviewed.jsonl")

    print(f"Reading from: {input_path}")
    print(f"Writing to: {output_path}")

    processed = 0
    accept_total = 0
    reject_total = 0

    # Track label distribution using majority voting across all judges
    label_counts = {'functional': 0, 'brandable': 0, 'ambiguous': 0}
    all_labels_across_judges = {'functional': 0, 'brandable': 0, 'ambiguous': 0}

    with open(input_path, "r", encoding="utf-8") as infile, \
         open(output_path, "w", encoding="utf-8") as outfile:

        for line in infile:
            record = json.loads(line)

            # Only process pass records
            if record.get("screen_result") != "pass":
                continue

            processed += 1
            result = process_record(record)
            outfile.write(json.dumps(result, ensure_ascii=False) + "\n")

            # Track statistics
            summary = result.get("primary_summary", {})
            votes = result.get("primary_votes", [])

            # Count all labels from all judges for overall distribution
            for vote in votes:
                if vote.get("decision") == "accept":
                    label = vote.get("label")
                    if label in all_labels_across_judges:
                        all_labels_across_judges[label] += 1

            if summary.get("accept", 0) >= 3:  # Majority accept
                accept_total += 1

                # Determine majority label for this word
                accept_votes = [v for v in votes if v.get("decision") == "accept"]
                if accept_votes:
                    # Count labels from accepting judges
                    label_counter = {}
                    for vote in accept_votes:
                        label = vote.get("label")
                        if label:
                            label_counter[label] = label_counter.get(label, 0) + 1

                    # Get majority label (or most common if tie)
                    if label_counter:
                        majority_label = max(label_counter, key=label_counter.get)
                        if majority_label in label_counts:
                            label_counts[majority_label] += 1
            else:
                reject_total += 1

            if processed % 100 == 0:
                print(f"Processed: {processed} records...")

    print(f"\n" + "="*60)
    print(f"Primary Review Complete!")
    print(f"="*60)
    print(f"Total processed: {processed}")
    print(f"Majority accept:  {accept_total} ({accept_total/processed*100:.1f}%)")
    print(f"Majority reject:  {reject_total} ({reject_total/processed*100:.1f}%)")

    print(f"\nLabel Distribution (majority vote per word):")
    total_labeled = sum(label_counts.values())
    for label, count in label_counts.items():
        if total_labeled > 0:
            pct = (count / total_labeled * 100)
            print(f"  {label}: {count} ({pct:.1f}%)")

    print(f"\nLabel Distribution (all judge votes):")
    total_all_votes = sum(all_labels_across_judges.values())
    for label, count in all_labels_across_judges.items():
        if total_all_votes > 0:
            pct = (count / total_all_votes * 100)
            print(f"  {label}: {count} ({pct:.1f}%)")

    print(f"Output: {output_path}")
    print(f"="*60)

if __name__ == "__main__":
    main()
