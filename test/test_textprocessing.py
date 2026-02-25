import pytest
# Add the src directory to the path.
import sys
import os
# Check, if the src directory is in the path (resolves test discovery failing)
if os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) not in sys.path:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.textprocessing import split_balanced
from src.textprocessing import REGEX

def test_split_balanced():

    test_sentence = 'This is a, test- sentence.'
    target_sentences = ['This is a,', 'test- sentence.']
    sen1, sen2 = split_balanced(test_sentence, REGEX)
    assert sen1 == target_sentences[0]
    assert sen2 == target_sentences[1]

    test_sentence = 'This, is a test sentence.'
    sen1, sen2 = split_balanced(test_sentence, REGEX)
    target_sentences = ['This,', 'is a test sentence.']
    assert sen1 == target_sentences[0]
    assert sen2 == target_sentences[1]

    test_sentence = 'This is a test, sentence.'
    sen1, sen2 = split_balanced(test_sentence, REGEX)
    target_sentences = ['This is a test,', 'sentence.']
    assert sen1 == target_sentences[0]
    assert sen2 == target_sentences[1]

    test_sentence = 'This is a test. sentence.'
    sen1, sen2 = split_balanced(test_sentence, REGEX)
    target_sentences = ['This is a test.', 'sentence.']
    assert sen1 == target_sentences[0]
    assert sen2 == target_sentences[1]

    test_sentence = '» This is a test.« sentence.'
    sen1, sen2 = split_balanced(test_sentence, REGEX)
    target_sentences = ['» This is a test.«', 'sentence.']
    assert sen1 == target_sentences[0]
    assert sen2 == target_sentences[1]

    test_sentence = 'Er bearbeitete meine Schulter und den Rücken mit seinen Riesenhänden, und einmal sagte ich im Spaß: »Sie sollten Pizzateig kneten.«'
    sen1, sen2 = split_balanced(test_sentence, REGEX)
    target_sentences = ['» This is a test.«', 'sentence.']
    assert sen1 == target_sentences[0]
    assert sen2 == target_sentences[1]
