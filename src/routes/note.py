import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, request
from src.models.note import Note, db

note_bp = Blueprint('note', __name__)

@note_bp.route('/translate', methods=['POST'])
def translate_text():
    data = request.get_json(silent=True)
    text = data.get('text') if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify({'error': 'Text is required'}), 400
    text = text.strip()

    api_key = os.environ.get('GENAI_API_KEY')
    if not api_key:
        return jsonify({
            'error': 'Set GENAI_API_KEY in the app environment and restart the app to enable translation',
        }), 503

    payload = {
        'model': 'DeepSeek-V4-Flash',
        'stream': False,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'Detect whether the input is English or Chinese. Translate English into '
                    'Traditional Chinese (Hong Kong usage), or Chinese into English. Preserve '
                    'the original meaning, line breaks, and formatting. Return only the translation.'
                ),
            },
            {'role': 'user', 'content': text},
        ],
    }
    provider_request = Request(
        'https://genai.comp.polyu.edu.hk/api/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urlopen(provider_request, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
        translated_text = result['choices'][0]['message']['content']
        if not isinstance(translated_text, str) or not translated_text.strip():
            raise ValueError('The translation service returned empty text')
        translated_text = translated_text.strip()
        return jsonify({'translation': translated_text})
    except HTTPError as error:
        return jsonify({'error': f'Translation service returned HTTP {error.code}'}), 502
    except (URLError, TimeoutError):
        return jsonify({'error': 'Could not connect to the translation service'}), 502
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return jsonify({'error': 'The translation service returned an invalid response'}), 502

@note_bp.route('/notes', methods=['GET'])
def get_notes():
    """Get all notes, ordered by most recently updated"""
    notes = Note.query.order_by(Note.updated_at.desc()).all()
    return jsonify([note.to_dict() for note in notes])

@note_bp.route('/notes', methods=['POST'])
def create_note():
    """Create a new note"""
    try:
        data = request.json
        if not data or 'title' not in data or 'content' not in data:
            return jsonify({'error': 'Title and content are required'}), 400
        
        note = Note(title=data['title'], content=data['content'])
        db.session.add(note)
        db.session.commit()
        return jsonify(note.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    """Get a specific note by ID"""
    note = Note.query.get_or_404(note_id)
    return jsonify(note.to_dict())

@note_bp.route('/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """Update a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        note.title = data.get('title', note.title)
        note.content = data.get('content', note.content)
        db.session.commit()
        return jsonify(note.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Delete a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        db.session.delete(note)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/search', methods=['GET'])
def search_notes():
    """Search notes by title or content"""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    notes = Note.query.filter(
        (Note.title.contains(query)) | (Note.content.contains(query))
    ).order_by(Note.updated_at.desc()).all()
    
    return jsonify([note.to_dict() for note in notes])

