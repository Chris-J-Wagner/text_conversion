import numpy as np
from matplotlib import pyplot as plt
from docx import Document
import re
import os

# Constants.

token2placeholder = {'...' : '<dots>'}
placeholder2token = {v : k for k, v in token2placeholder.items()}
REGEX = r'\.«|,|-|–|:|\.|\?|\!'

# Functions.

def plot_histogram(word_lens: list[int], title: str):
    """ Plot a histogram of the number of words in sentences.
    Args:
        word_lens (list[int]): list of number of words in sentences.
        title (str): title of the plot.
    Returns:
        None
    """

    fig, ax = plt.subplots(1,1, figsize=(5, 5))
    ax.hist(word_lens, bins=np.arange(0, max(word_lens) + 1, 1))
    ax.set_title(title)
    ax.set_xlabel("Number of words")
    ax.set_ylabel("Number of sentences")

    return fig


def get_paragraphs(document: Document, replacement_tokens = None, is_verbose = True):
    """ Get all paragraphs from a document and remove formatting. 
    Args:
        document (docx.Document): document to extract paragraphs from.
        removal_tokens (dict): dict of tokens with their replacement token to replace in the text.
    Returns:
        text (list[str]): list of paragraphs (str
    """

    text = []
    for par in document.paragraphs:
        par = par.text.lstrip().rstrip()

        # Replace tokens that should permamently be altered.
        if replacement_tokens:
            for token, placeholder in replacement_tokens.items():
                par = par.replace(token, placeholder)

        # Replace tokens with placeholders that are recovered again.
        for token, placeholder in token2placeholder.items():
            par = par.replace(token, placeholder)
        text.append(par)

    if is_verbose:
        print(f"{len(document.sections)} sections in document.")
        print(f"{len(text)} paragraphs in document")

    return text


def split_balanced(sentence: str, regex: str):
    """Split a sentence into two balanced sentences based on the regex
    list.
    Args:
        sentence (str): sentence to split.
        regex (str): regular expression to split the sentence on.
    Returns:
        (sentence_1, sentence_2) (tuple): tuple of the two sentences.
    """
    
    words = sentence.split(' ')

    # Remove empty words.
    words = [w for w in words if w != '']
    
    num_words = len(words)

    splits = re.split(regex, sentence)
    splits = [s.lstrip().rstrip() for s in splits]

    split_delimiter = re.findall(regex, sentence)

    assert len(splits) == len(split_delimiter) + 1

    split_lens = [len(s.split(' ')) for s in splits]
    split_lens_cum = np.cumsum(split_lens)
    idx = np.where(split_lens_cum > (num_words // 2 + 1))[0][0]

    # If the index is 0, split at the first sentence.
    if idx == 0:
        idx = 1
        
    # Add all but the split delimiters back to the sentence.
    sentence_1 = ''
    sentence_2 = ''

    split_delimiter = split_delimiter + [''] # Add empty delimiter at the end to equal its length to the number of splits.
    
    for data in zip(splits[:idx],split_delimiter[:idx]):
        sen, delim = data
        sentence_1 += sen + delim + ' '

    for data in zip(splits[idx:],split_delimiter[idx:]):
        sen, delim = data
        sentence_2 += sen + delim + ' '

    sentence_1 = sentence_1.rstrip()
    sentence_2 = sentence_2.rstrip()

    return (sentence_1, sentence_2)


def merge_sentences(sentences: list[str], MIN_NUM_WORDS: int):
    """ Merge sentences into a list of sentences with a minimum number of words.
    Args:
        sentences (list[str]): list of sentences to merge.
        MIN_NUM_WORDS (int): minimum number of words in a sentence.
    Returns:
        merged_sentences (list[str]): list of sentences with a minimum number of words.
        word_lens (list[int]): list of number of words in each sentence.
    """

    merged_sentences = []
    word_lens = []
    num_words = 0
    sentence = ''

    for sen in sentences:

        num_words += len(sen.split(' '))
        sentence = " ".join([sentence, sen])

        if num_words >= MIN_NUM_WORDS:
            merged_sentences.append(sentence.lstrip())
            word_lens.append(num_words)
            num_words = 0
            sentence = ''

    return merged_sentences, word_lens


def split_long_sentences(sentences: list[str], max_num_words: int, regex: str):
    """Split long sentences into two balanced sentences.
    Args:
        sentences (list[str]): list of sentences to split.
        max_num_words (int): maximum number of words in a sentence.
        regex (str): regular expression to split the sentence on.
    Returns:
        split_sentences (list[str]): list of sentences with a maximum number of words.
    Note:
        The maximum number of words is not guaranteed to be met, since the split is based on interpunctiations.
        Same applies for the minimal number of words.
    """

    split_sentences = []
    word_lens = []

    for sen in sentences:
        
        num_words = len(sen.split(' '))

        if num_words > max_num_words:
            sen1, sen2 = split_balanced(sen, regex)
            split_sentences.append(sen1)
            split_sentences.append(sen2)

            # Append the number of words in each sentence.
            word_lens.append(len(sen1.split(' ')))
            word_lens.append(len(sen2.split(' ')))
        else:
            split_sentences.append(sen)
            word_lens.append(len(sen.split(' ')))

    return split_sentences, word_lens


    
def export_as_altavo_studio_format(sentences: list[str], 
                                   language: str,
                                   output_path: str = None):
    """Export the split sentences as a text file in the Altavo Studio format, including
    the phonemized version of the sentence and a unique id.
    Args:
        sentences (list[str]): list of sentences.
        output_path (str, Optional): path to save the .csv file. If None, will save to the current directory.
    Returns:
        None
    """

    altavo_studio_pars = []

    try:
        from altavo_mlmodules.textprocessing import PhonemizerTranscription
    except ImportError as exc:
        raise RuntimeError(
            "altavo_mlmodules is required for export_as_altavo_studio_format. "
            "Remove this call or install the proprietary package."
        ) from exc

    phonemizer = PhonemizerTranscription()

    for idx, sen in enumerate(sentences):
        if idx % 50 == 0:
            print(f'At index {idx}')
        tx_idxs = phonemizer(sen, language=language)
        tx = ''.join(phonemizer.decode(tx_idxs))

        if '<oov>' in tx:
            raise RuntimeError(f"OOV token in paragraph {idx}, {tx}.")
        altavo_studio_pars.append(f"{idx}|{sen}|{tx}")

    if output_path is None:
        output_path = os.getcwd() + '/altavo_studio_export.csv'

    with open(output_path, 'w') as f:
        for sen in altavo_studio_pars:
            f.write(sen + '\n')
