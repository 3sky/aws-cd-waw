"""
Get the localization of video
"""
import codecs
import json
import logging
import os
import re
import sys
from contextlib import closing
from time import gmtime, strftime

import boto3
from botocore.exceptions import ClientError
from moviepy import editor
from moviepy.editor import *
from moviepy.video.tools.subtitles import SubtitlesClip


logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


def new_phrase():
    """
    simply create a phrase tuple
    """
    return {'start_time': '', 'end_time': '', 'words': []}


def get_time_code(seconds):
    """
    Format and return a string that contains the converted number of seconds into SRT format

    param: seconds: the duration in seconds to convert to HH:MM:SS,mmm
    return: the formatted string in HH:MM:SS,mmm format

    """
    t_hund = int(seconds % 1 * 1000)
    t_seconds = int(seconds)
    t_secs = ((float(t_seconds) / 60) % 1) * 60
    t_mins = int(t_seconds / 60)
    return f"00:{t_mins:02d}:{int(t_secs):02d},{t_hund:03d}"


def write_transcript_to_srt(transcript, srt_file_name):
    """
    Function to get the phrases from the transcript and write it out to an SRT file

    param: transcript: the JSON output from Amazon Transcribe
    param: source_lang_code: the language code for the original content (e.g. English = "EN")
    param: srtFileName: the name of the SRT file (e.g. "mySRT.SRT")

    """

    # Write the SRT file for the original language
    logging.info("==> Creating SRT from transcript")
    phrases = get_phrases_from_transcript(transcript)
    write_srt(phrases, srt_file_name)


def get_phrases_from_transcript(transcript):
    """
    Based on the JSON transcript provided by Amazon Transcribe,
          get the phrases from the translation
          and write it out to an SRT file

    param: transcript: the JSON output from Amazon Transcribe

    This function is intended to be called with the JSON
    structure output from the Transcribe service.  However,
    if you only have the translation of the transcript,
    then you should call get_phrases_from_translation instead
    """

    with open(transcript, 'r', encoding='utf-8') as file:
        data = file.read()
    transcript_contnet = json.loads(data)
    # Now create phrases from the translation
    items = transcript_contnet['results']['items']

    # set up some variables for the first pass
    phrase = new_phrase()
    phrases = []
    n_phrase = True
    counter_x = 0
    counter_c = 0

    logging.info("==> Creating phrases from transcript...")

    for item in items:

        # if it is a new phrase, then get the start_time of the first item
        if n_phrase is True:
            if item["type"] == "pronunciation":
                phrase["start_time"] = get_time_code(float(item["start_time"]))
                n_phrase = False
            counter_c += 1
        else:
            # get the end_time if the item is a pronuciation and store it
            # We need to determine if this pronunciation or puncuation here
            # Punctuation doesn't contain timing information, so we'll want
            # to set the end_time to whatever the last word in the phrase is.
            if item["type"] == "pronunciation":
                phrase["end_time"] = get_time_code(float(item["end_time"]))

        # in either case, append the word to the phrase...
        phrase["words"].append(item['alternatives'][0]["content"])
        counter_x += 1

        # now add the phrase to the phrases, generate a new phrase, etc.
        if counter_x == 10:
            phrases.append(phrase)
            phrase = new_phrase()
            n_phrase = True
            counter_x = 0

    return phrases


def write_translation_to_srt(transcript, source_lang_code, target_lang_code, srt_file_name, region):
    """
    Based on the JSON transcript provided by Amazon Transcribe,
    get the phrases from the translation and write it out to an SRT file

    param: transcript: The JSON output from Amazon Transcribe.
    param: source_lang_code: The language code for the original content (e.g. English = "EN").
    param: target_lang_code: The language code for the translated content (e.g. Spanish = "ES").
    param: srt_file_name: The name of the SRT file (e.g. "mySRT.srt").
    param: region: The name of the region
    """

    # First get the translation
    logging.info("\n\n==> Translating from " +
                 source_lang_code + " to " + target_lang_code)
    translation = translate_transcript(
        transcript, source_lang_code, target_lang_code, region)

    # Now create phrases from the translation
    text_to_translate = translation["TranslatedText"]
    phrases = get_phrases_from_translation(
        text_to_translate, target_lang_code, region)
    write_srt(phrases, srt_file_name)


def get_phrases_from_translation(translation, target_lang_code, region):
    """
    Based on the JSON translation provided by Amazon Translate,
    get the phrases from the translation and write it out to an SRT file.
    Note that since we are using a block of translated text rather than
    a JSON structure with the timing for the start and end of each word as in
    the output of Transcribe, we will need to calculate the start and end-time
    for each phrase.

    param: translation: The JSON output from Amazon Translate.
    param: target_lang_code: The language code for the translated content (e.g. Spanish = "ES").
    """
    # Now create phrases from the translation
    words = translation.split()

    # set up some variables for the first pass
    phrase = new_phrase()
    phrases = []
    n_phrase = True
    counter_x = 0
    counter_c = 0
    seconds = 0

    logging.info("==> Creating phrases from translation...")

    for word in words:

        # if it is a new phrase, then get the start_time of the first item
        if n_phrase is True:
            phrase["start_time"] = get_time_code(seconds)
            n_phrase = False
            counter_c += 1

        # Append the word to the phrase...
        phrase["words"].append(word)
        counter_x += 1

        # now add the phrase to the phrases, generate a new phrase, etc.
        if counter_x == 10:

            # For Translations, we now need to calculate the end time for the phrase
            psecs = get_seconds_from_translation(get_phrase_text(
                phrase), target_lang_code, "phraseAudio" + str(counter_c) + ".mp3", region)
            seconds += psecs
            phrase["end_time"] = get_time_code(seconds)

            phrases.append(phrase)
            phrase = new_phrase()
            n_phrase = True
            # seconds += .001
            counter_x = 0

        # This if statement is to address a defect in the SubtitleClip.
        # If the Subtitles end up being
        # a different duration than the content, MoviePy will
        # sometimes fail with unexpected errors while
        # processing the subclip.   This is limiting it to something
        # less than the total duration for our example
        # however, you may need to modify or eliminate this line
        # depending on your content.
        if counter_c == 30:
            break

    return phrases


def translate_transcript(transcript, source_lang_code, target_lang_code, region):
    """
    Based on the JSON transcript provided by Amazon Transcribe,
    get the JSON response of translated text

    param: transcript: The JSON output from Amazon Transcribe.
    param: source_lang_code: The language code for the original content (e.g. English = "EN").
    param: target_lang_code: The language code for the translated content (e.g. Spanish = "ES").
    param: region: The AWS region in which to run the Translation (e.g. "us-east-1").
    """
    # Get the translation in the target language.
    # We want to do this first so that the translation is in
    # the full context of what is said vs. 1 phrase at a time.
    # This really matters in some lanaguages

    # stringify the transcript
    with open(transcript, 'r',  encoding='utf-8') as file:
        data = file.read()

    transcript_source = json.loads(data)

    # pull out the transcript text and put it in the txt variable
    txt = transcript_source["results"]["transcripts"][0]["transcript"]

    # set up the Amazon Translate client
    translate = boto3.client(service_name='translate',
                             region_name=region, use_ssl=True)

    # call Translate  with the text, source language code,
    # and target language code.  The result is a JSON structure containing the
    # translated text
    translation = translate.translate_text(
        Text=txt, SourceLanguageCode=source_lang_code, TargetLanguageCode=target_lang_code)

    return translation


def write_srt(phrases, filename):
    """
    Iterate through the phrases and write them to the SRT file

    param: phrases: the array of JSON tuples containing the phrases to show up as subtitles
    param: filename: the name of the SRT output file (e.g. "mySRT.srt")

    """
    logging.info("==> Writing phrases to disk...")

    # open the files
    with codecs.open(filename, "w+", "utf-8") as encoded_file:
        iteration = 1

        for phrase in phrases:

            # write out the phrase number
            encoded_file.write(str(iteration) + "\n")
            iteration += 1

            # write out the start and end time
            encoded_file.write(phrase["start_time"] +
                               " --> " + phrase["end_time"] + "\n")

            # write out the full phase.  Use spacing if it is a word, or punctuation without spacing
            out = get_phrase_text(phrase)

            # write out the srt file
            encoded_file.write(out + "\n\n")

        encoded_file.close()


def get_phrase_text(phrase):
    """
    For a given phrase, return the string of words including punctuation

    param: phrase: the array of JSON tuples containing the words to show up as subtitles
    """
    length = len(phrase["words"])

    out = ""
    for i in range(0, length):
        phrase_based_on_iteration = phrase["words"][i]
        if re.match('[a-zA-Z0-9]', phrase_based_on_iteration):
            if i > 0:
                out += " " + phrase_based_on_iteration
            else:
                out += phrase_based_on_iteration
        else:
            out += phrase_based_on_iteration

    return out


def annotate(clip, txt, txt_color='white', fontsize=24, font='Space-Mono-Italic-for-Powerline'):
    """
    This function creates a TextClip based on the provided text and composites
    the subtitle onto the provided clip. Defaults are used for txt_color, fontsize,
    and font. You can override them as desired.

    param: clip: The clip to composite the text on.
    param: txt: The block of text to composite on the clip.
    param: txt_color: The color of the text on the screen. (optional)
    param: font_size: The size of the font to display. (optional)
    param: font: The font to use for the text. (optional)
    """
    # Writes a text at the bottom of the clip  'Xolonium-Bold'
    txtclip = editor.TextClip(
        txt, fontsize=fontsize, font=font, color=txt_color).on_color(color=[0, 0, 0])
    cvc = editor.CompositeVideoClip([clip, txtclip.set_pos(('center', 50))])
    return cvc.set_duration(clip.duration)


def get_current_time():
    """
    This function returns the current time in seconds
    """
    return strftime("%H:%M:%S", gmtime())


def create_video(original_clip_name,
                 subtitles_file_name,
                 output_file_name,
                 alternate_audio_file_name,
                 use_original_audio=True):
    """
    This function drives the MoviePy code needed to put
    all of the pieces together and create a new subtitled video

    param: original_clip_name:  the flename of 
                                the orignal conent (e.g. "originalVideo.mp4")
    param: subtitles_file_name: the filename of the SRT file (e.g. "mySRT.srt")
    param: output_file_name: the filename of the output video 
                                file (e.g. "output_file_name.mp4")
    param: alternate_audio_file_name: the filename of an MP3 file 
                                that should be used to replace the audio track
    param: use_original_audio: boolean value as to whether or not we should 
                                leave the orignal audio in place or overlay it

    """
    logging.info("\n==> createVideo ")

    # Load the original clip
    logging.info(f"\t %s Reading video clip: %s " %
                 (get_current_time(), original_clip_name))

    clip = VideoFileClip(original_clip_name)

    logging.info("\t\t==> Original clip duration: " + str(clip.duration))
    if use_original_audio is False:
        logging.info(f"\t %s Reading alternate audio track: %s " %
                     (get_current_time(), alternate_audio_file_name))
        audio = AudioFileClip(alternate_audio_file_name)
        audio = audio.subclip(0, clip.duration)
        audio.set_duration(clip.duration)
        logging.info("\t\t==> Audio duration: " + str(audio.duration))
        clip = clip.set_audio(audio)
    else:
        logging.info(f"\t %s Using original audio track... " %
                     (get_current_time()))

    # Create a lambda function that will be used to generate the subtitles for each sequence in the SRT
    def generator(txt): return TextClip(
        txt, font='Arial-Bold', fontsize=24, color='white')

    # read in the subtitles files
    logging.info(f"\t %s Reading subtitle file: %s " %
                 (get_current_time(), subtitles_file_name))

    subs = SubtitlesClip(subtitles_file_name, generator)

    logging.info("\t\t==> Subtitles duration before: " + str(subs.duration))
    subs = subs.subclip(0, clip.duration - .001)
    subs.set_duration(clip.duration - .001)
    logging.info("\t\t==> Subtitles duration after: " + str(subs.duration))
    logging.info(f"\t %s Reading subtitle file complete: %s " %
                 (get_current_time(), subtitles_file_name))

    logging.info(f"\t %s Creating Subtitles Track... " %
                 (get_current_time()))

    annotated_clips = [annotate(clip.subclip(from_t, to_t), txt)
                       for (from_t, to_t), txt in subs]

    logging.info(f"\t %s Creating composited video: %s " %
                 (get_current_time(), output_file_name))

    # Overlay the text clip on the first video clip
    final = concatenate_videoclips(annotated_clips)

    logging.info(f"\t %s Writing video file: %s " %
                 (get_current_time(), output_file_name))

    final.write_videofile(output_file_name)


def write_audio(output_file, stream):
    """
    Writes the bytes associated with the stream to a binary file

    :param output_file: the name + extension of the ouptut file (e.g. "abc.mp3")
    :param stream: the stream of bytes to write to the output_file

    Example:
    >>> write_audio("abc.mp3", stream)

    Note:
    The function will create a new audio file with the name 
    provided in the audio_file_name parameter.
    If the file already exists, it will be overwritten.

    Note:
    The function will create a new audio file with the name 
    provided in the audio_file_name parameter.
    If the file already exists, it will be overwritten.
    """

    my_bytes = stream.read()

    logging.info("\t==> Writing " + str(len(my_bytes)) +
                 "bytes to audio file: " + output_file)
    try:
        # Open a file for writing the output as a binary stream
        with open(output_file, "wb") as file:
            file.write(my_bytes)

        if file.closed:
            logging.info("\t==>" + output_file + " is closed")
        else:
            logging.info("\t==>" + output_file + " is NOT closed")
    except IOError as error:
        # Could not write to file, exit gracefully
        logging.info(error)
        sys.exit(-1)


def create_audio_track_from_translation(transcript, source_lang_code,
                                        target_lang_code, audio_file_name, region):
    """
    Using the provided transcript, get a translation from Amazon Translate, 
    then use Amazon Polly to synthesize speech

    :param transcript: the Amazon Transcribe JSON structure to translate
    :param source_lang_code: the language code for the original content (e.g. English = "EN")
    :param target_lang_code: the language code for the translated content (e.g. Spanich = "ES")
    :param audio_file_name: the name (including extension) of the target audio file (e.g. "abc.mp3")
    :param region: the aws region in which to run the service

    Example:
    >>> create_audio_track_from_translation(transcript, "EN", "ES", "abc.mp3", "us-east-1")

    Note:
    The function will create a new audio 
    file with the name provided in the audio_file_name parameter.
    If the file already exists, it will be overwritten.

    Note:
    The function will create a new audio file 
    with the name provided in the audio_file_name parameter.
    If the file already exists, it will be overwritten.
    """
    logging.info("\n==> create_audio_track_from_translation ")

    # Set up the polly and translate services
    client = boto3.client('polly', region_name=region)
    translate = boto3.client(service_name='translate',
                             region_name=region, use_ssl=True)

    # get the transcript text
    with open(transcript, 'r', encoding='utf-8') as file:
        data = file.read()
    temp = json.loads(data)
    transcript_txt = temp["results"]["transcripts"][0]["transcript"]

    voice_id = get_voice_id(target_lang_code)

    # Now translate it.
    translated_txt = translate.translate_text(Text=transcript_txt,
                                              SourceLanguageCode=source_lang_code,
                                              TargetLanguageCode=target_lang_code
                                              )["TranslatedText"][:2999]

    # Use the translated text to create the synthesized speech
    response = client.synthesize_speech(
        OutputFormat="mp3", SampleRate="22050", Text=translated_txt, VoiceId=voice_id)

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        logging.info("\t==> Successfully called Polly for speech synthesis")
        write_audio_stream(response, audio_file_name)
    else:
        logging.info("\t==> Error calling Polly for speech synthesis")


def write_audio_stream(response, audio_file_name):
    """
    Utility to write an audio file from the response from the Amazon Polly API

    :param response: the Amazaon Polly JSON response
    :param audio_file_name: the name (including extension) of the target audio file (e.g. "abc.mp3")

    Example:
    >>> response = client.synthesize_speech(
    ...     OutputFormat="mp3", SampleRate="22050", Text="Hello World", voice_id="Aditi")
    >>> write_audio_stream(response, "abc.mp3")
    """

    # Take the resulting stream and write it to an mp3 file
    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            output = audio_file_name
            write_audio(output, stream)


def get_voice_id(target_lang_code):
    """
    Utility to return the name of the voice to use given a language code.
    Refer to the Amazon Polly API documentation for other voice_id names

    :param target_lang_code: the language code used for the target Amazon Polly output
    :return: the name of the voice to use for the target language (e.g. "Brian")

    Example:
    >>> get_voice_id("es")
    'Penelope'
    >>> get_voice_id("de")
    'Marlene'
    >>> get_voice_id("en")
    'Joanna'
    >>> get_voice_id("fr")
    'Celine'
    >>> get_voice_id("it")
    'Carla'
    >>> get_voice_id("ja")
    'Mizuki'
    >>> get_voice_id("ko")
    'Seoyeon'
    >>> get_voice_id("pt")
    'Vitoria'
    """

    if target_lang_code == "es":
        voice_id = "Penelope"
    elif target_lang_code == "de":
        voice_id = "Marlene"
    elif target_lang_code == "fr":
        voice_id = "Celine"
    elif target_lang_code == "it":
        voice_id = "Carla"
    elif target_lang_code == "pt":
        voice_id = "Vitoria"

    return voice_id


def get_seconds_from_translation(text_to_synthesize, target_lang_code, audio_file_name, region):
    """
    Utility to determine how long in seconds it will 
    take for a particular phrase of translated text to be spoken

    :param text_to_synthesize: the raw text to be synthesized
    :param target_lang_code: the language code used for the target Amazon Polly output
    :param audio_file_name: the name (including extension) of the target audio file (e.g. "abc.mp3")
    """

    # Set up the polly and translate services
    client = boto3.client('polly', region_name=region)
    boto3.client(service_name='translate',
                 region_name=region, use_ssl=True)

    # Use the translated text to create the synthesized speech
    response = client.synthesize_speech(
        OutputFormat="mp3", SampleRate="22050",
        Text=text_to_synthesize, VoiceId=get_voice_id(target_lang_code))

    # write the stream out to disk so that we can load it into an AudioClip
    write_audio_stream(response, audio_file_name)

    # Load the temporary audio clip into an AudioFileClip
    audio = AudioFileClip(audio_file_name)

    # return the duration
    return audio.duration


def download_file_from_s3(input_file_name, output_file_name):
    """Upload a file to an S3 bucket

    :param input_file_name: input file in format s3://
    :param output_file_name: S3 object name after download
    :return: True if file was uploaded, else False
    """
    if not input_file_name.startswith('s3://'):
        logging.error("Wrong input filename")
        return False

    # Remove the 's3://' prefix
    path_without_prefix = input_file_name[5:]
    # Split the path into bucket and object parts
    bucket_name, object_name = path_without_prefix.split('/', 1)
    s3_client = boto3.client('s3')
    try:
        s3_client.download_file(bucket_name, object_name, output_file_name)
    except ClientError as local_error:
        logging.error(local_error)
        return False
    return True


def upload_file_to_s3(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as local_error:
        logging.error(local_error)
        return False
    return True


def parse_infile_to_outfile(infile, used_language):
    """ Parse infile name into final video name

    :param infile: File name in format s3://path/to/file.mp4
    :param used_language: Language extension
    :return: String with expected name
    """

    path_parts = infile.split('/')

    # Get the last part of the path (filename with extension)
    filename = path_parts[-1]

    # Remove the file extension
    filename_without_extension = filename.split('.')[0]

    # Extract the desired word
    desired_word = filename_without_extension

    return desired_word + "-" + used_language + ".mp4"


# ==================================================================================
# Main control loop
# ==================================================================================

INVIDEO = os.getenv('INVIDEO')
INSUBTITLES = os.getenv('INSUBTITLES')
OUTBUCKET = os.getenv('OUTBUCKET')
OUTLANG = os.getenv('OUTLANG')
REGION = os.getenv('REGION')

download_file_from_s3(INVIDEO, "video.mp4")
download_file_from_s3(INSUBTITLES, "transcribe.json")
write_transcript_to_srt("transcribe.json", "subtitles-en.srt")
create_video('video.mp4', "subtitles-en.srt",
             "result-en.mp4",
             "audio-en.mp3", True)

# Now write out the translation to the transcript for each of the target languages
for lang in OUTLANG.split():
    write_translation_to_srt("transcribe.json", 'en', lang,
                             "subtitles-" + lang + ".srt", REGION)

    # Now that we have the subtitle files, let's create the audio track
    create_audio_track_from_translation(
        "transcribe.json", 'en', lang, "audio-" + lang + ".mp3", REGION)

    # Finally, create the composited video
    create_video("video.mp4", "subtitles-" + lang + ".srt",
                 "video-" + lang + ".mp4", "audio-" + lang + ".mp3", False)
    upload_file_to_s3("video-" + lang + ".mp4", OUTBUCKET,
                      parse_infile_to_outfile(INVIDEO, lang))
