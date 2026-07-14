import pytest

from text_conversion.textprocessing import split_balanced
from text_conversion.textprocessing import REGEX

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
    target_sentences = [
        'Er bearbeitete meine Schulter und den Rücken mit seinen Riesenhänden,',
        'und einmal sagte ich im Spaß: »Sie sollten Pizzateig kneten.«',
    ]
    assert sen1 == target_sentences[0]
    assert sen2 == target_sentences[1]
