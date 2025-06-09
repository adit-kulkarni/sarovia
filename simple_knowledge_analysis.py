import json
import requests
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')

# All your Spanish messages extracted from the database
messages = [
    'Hola, me llamo Adit. No me gusta fotografía mucho, pero necesito aprender.',
    'Sí, yo tengo una Fujifilm cámara.',
    'Es muy bien.',
    'Yo use para...',
    'Ocho meses ahora.',
    'Estaba viajando para ocho meses. Entonces...',
    'Y muchas gracias. Un saludo.',
    'Por ejemplo, yo tomo fotografía.',
    'para las montañas.',
    'Me gusta las montañas.',
    'Pero también las playas.',
    '¿Y las fotos van bien?',
    '¿Cómo se dice, the photos look beautiful, en español?',
    'Las fotos se ven hermosas.',
    '¿Qué significa...?',
    'Sí, tengo un plan para usar mi cámara.',
    'Mañana voy a Badalona.',
    'Quiero...',
    'Hago un fotos.',
    '¿Otra vez, porfa?',
    'Sí, sí. Y.',
    '¿Dónde naciste?',
    'Nací en Londres. Yo crecí en Manchester.',
    'Fui a university in...',
    'en cerca a Birmingham.',
    'Pero yo trabajé.',
    'para cinco años en Londres.',
    'Hola.',
    'Necesito practicar hablar español.',
    'porque',
    'Hay una chica en...',
    'Estados Unidos',
    'Y ella quiere...',
    'hablar español conmigo.',
    'Bien.',
    'Hola.',
    'Necesito practicar hablar español porque...',
    'Hay una chica en Estados Unidos y...',
    'Ella quiere hablar español conmigo.',
    'No conozco estos parques.',
    'Me llamo Adit. Estoy aquí para...',
    'La fotografía también.',
    'Me gustan los paisajes más. ¿Y a ti?',
    'Me gusta hacer fotos en la playa.',
    '¿Conoces un buen lugar para eso?',
    'Sí, me gustaría mucho.',
    '¿Cuándo es el mejor momento para visitar Playa Blanca?',
    'Sí, me encantaría planear una visita en primavera.',
    '¿Qué más puedo hacer en Playa Blanca?',
    'Necesito una mesa para cuatro personas, por favor.',
    'Quisiera escuchar las especialidades del día, por favor.',
    '¿Qué significa orden?',
    'Sí, por favor, escuche buena.',
    '¿Qué vinos tienes?',
    'Creo que...',
    'Tengo...',
    'Vino tinto.',
    '¿Cuántos minutos va a hacer?',
    'Necesito una mesa para tres personas.',
    '¿Qué significa mientras?',
    '¿Puedes explicar esto en inglés?',
    'Gracias. Adelante.',
    '¿Nos gustaría probar la sangría de la casa, porfa?',
    'Es todo, gracias.',
    '¡Hola!',
    'Sí, todo bien.',
    'Estoy inglés.',
    'Me gustó mucho el café.',
    'Yo prefiero con leche.',
    '¿Qué significa acompañarlo?',
    '¿No puedes transcribir?',
    'Hola, ¿qué pasa?',
    'Me gustó la fotografía.',
    'No sé',
    'Necesito una mesa para tres.',
    '¡Gracias por ver el vídeo!',
    'Y nos vemos en el próximo video, ¡hasta la próxima!',
    'Necesito una mesa para tres, porfa.',
    'Sí, ¿puedo ver la carta, por favor?',
    'Sí, necesito una recomendación.',
    'Me gusta.',
    'Pescado.',
    'Hola, estoy bien. Me llamo Adit.',
    '¿Y cuántos años tienes?',
    'Oh, sí. Sí, sí. Esos ojos rojos. Eso es perfecto.',
    'Esa es la A.I.',
    'y nos vemos en el próximo video, ¡hasta la próxima!',
    'Quiero una cerveza, por favor.',
    'Ok, pausa.',
    'Si yo hablamos español.',
    'Así que hice un error.',
    'Así que esto es un error.',
    'Más lejos.',
    'Quisiera una recomendación.',
    'Mmm... no sé.',
    'Gracias.',
    'Sí, por favor.',
    'Me gusta la música.',
    'Quisiera una pizza.',
    '¿Cómo debería ordenar un restaurante? ¿Debería decir quisiera? ¿O debería decir puedes darme?',
    'sobre Puedes Traerme.',
    'si quiero practicar.',
    '¿Puedes traerme un poco pan?',
    '¡Sí quiero intentar!',
    'Yo hablo.',
    '¿Yo cómo?',
    'Yo vivimos.',
    'Yo vivo.',
    'Yo estudio.',
    'Yo trabajo.',
    'Yo como manzanas.',
    'Yo estudio en la escuela.',
    'Yo no trabajo mucho.',
    'Y yo hablo español.',
    'Yo vivo en Inglaterra.',
    'No es todo. Gracias.',
    'Hola, me llamo Adit. Buenos días.',
    'Adiós.',
    'Buenas tardes.',
    'Buenas noches, señorita.',
    'Hola, muy bien, gracias.',
    'Buenos días.',
    'Y buenas noches.',
    'Buenas tardes.',
    '¡Adiós!',
    'Hola.',
    'Adiós.',
    'Buenos días!',
    'Buenas tardes.',
    'Buenas noches.',
    'Me llamo Adit.',
    'Muchas gracias.',
    'Hasta luego.',
    'Hola, buenos días.',
    'Buenas tardes.',
    'Buenas noches.',
    '¡Hola!',
    'Adiós.',
    '¡Listo!',
    'Buenas tardes.',
    'Tengo un sándwich.',
    'Soy estudiante.',
    'Quiero un sándwich y un café.',
    'Tengo un café.',
    'Soy estudiante.',
    'Quiero agua.',
    'Sí, estoy listo.',
    'Lo siento.',
    'De nada.',
    '¿Qué significa no pasa nada?',
    'No pasa nada.',
    'de nada.',
    'Buenos días.',
    'Buenas tardes.',
    'Buenas noches.',
    'Muy interesante.',
    'Sí, por favor.',
    'Buenos días.',
    '1, 2, 3, 4',
    '5, 6, 7...',
    '¡Ocho!',
    'Estoy veinte y ocho.',
    'Tengo veinte y ocho.',
    'Tengo quince años.',
    'Tengo 28.',
    'Adiós.',
    'Mi color favorito es rojo.',
    'OK, genial.',
    '¿Cómo se dice yellow?',
    'Mi fruta favorita es mango.',
    'Mis zapatos son...',
    'negro',
    'Mi camisa es verde.',
    'Ok, yo llevo una...',
    'Camisa amarilla.',
    '¿Puedes explicar eso en inglés, por favor?',
    '¡Yo llevo una!',
    'Muchas gracias.',
    'Camiseta...',
    'genial',
    'No sé',
    '¿Puedes darme una lista de objetos de ropa y luego intentaré practicar diciéndolo?',
    '¡Gracias!',
    '¿Qué quieres que haga?',
    'Yo llevo una camisa.',
    'Yo tengo zapatos para hacer senderismo.',
    'cuando es',
    'Frio, yo llevo una suéter.',
    'Sí, yo tengo una chaqueta azul.',
    'Sí, cuando hace calor yo llevo...',
    'Pantalones cortos.',
    'Cuando yo juego deporte llevo...',
    'Ropa...',
    'Adelante',
    '¿Qué significa traje de baño?',
    'Sí, cuando...',
    'Voy a la playa.',
    'traje de baño',
    'Es todo, gracias.',
    'Yo soy una entrepreneur.',
    'Tengo una idea.',
    'Y era un café, por favor.',
    '¡Muy bien!',
    'Me llamo Adit, tengo 28 años y soy de Inglaterra.',
    'Sí, soy de Inglaterra, pero mis padres son indianos.',
    'Hola, me llamo Adit. Soy de Inglaterra. Mis padres son de India.',
    'Una vez de donde eres.',
    'Sí, creo que ellos hablan español en México y Guatemala y Perú y Bolivia también.',
    'Si, se hablan español en Brasil.',
    'No, gracias.'
]

def analyze_complete_knowledge():
    transcript = '\n'.join(messages)
    
    prompt = f"""Analyze the following es messages from a language learner. Extract vocabulary and grammar patterns they've used.

For each part of speech, provide a list of unique words/patterns the user has demonstrated:
- nouns: specific nouns they've used
- pronouns: pronouns they've used correctly
- adjectives: adjectives they've used
- verbs: for each verb, list the lemma and what tenses/persons they've used
- adverbs: adverbs they've used
- prepositions: prepositions they've used correctly
- conjunctions: conjunctions they've used
- articles: articles they've used correctly
- interjections: interjections they've used

Focus on words they used correctly and contextually appropriately. Don't include obvious mistakes.

Output ONLY a valid JSON object with this structure:
{{
  "nouns": ["word1", "word2"],
  "pronouns": ["word1", "word2"],
  "adjectives": ["word1", "word2"],
  "verbs": {{
    "lemma1": {{
      "present": ["1st_person", "3rd_person"],
      "past": ["1st_person"]
    }}
  }},
  "adverbs": ["word1", "word2"],
  "prepositions": ["word1", "word2"],
  "conjunctions": ["word1", "word2"],
  "articles": ["word1", "word2"],
  "interjections": ["word1", "word2"]
}}

Messages to analyze:
{transcript}"""

    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'gpt-4-turbo-preview',
            'messages': [{'role': 'system', 'content': prompt}],
            'temperature': 0.3,
            'max_tokens': 2500
        }
    )
    
    if response.status_code != 200:
        print(f'Error: {response.text}')
        return None
    
    response_data = response.json()
    result = response_data['choices'][0]['message']['content']
    
    # Clean and parse the JSON
    try:
        # Remove markdown formatting if present
        if result.startswith('```'):
            result = result.strip('```json').strip('```').strip()
        
        knowledge_data = json.loads(result)
        print(json.dumps(knowledge_data, indent=2, ensure_ascii=False))
        
        # Save to file for database update
        with open('complete_knowledge_result.json', 'w', encoding='utf-8') as f:
            json.dump(knowledge_data, f, indent=2, ensure_ascii=False)
        
        return knowledge_data
    except json.JSONDecodeError as e:
        print(f'JSON parse error: {e}')
        print(f'Raw result: {result}')
        return None

if __name__ == "__main__":
    result = analyze_complete_knowledge()
    if result:
        print("\n✅ Complete knowledge analysis completed successfully!")
        print("📁 Results saved to complete_knowledge_result.json")
    else:
        print("❌ Analysis failed") 