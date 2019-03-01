#!/usr/bin/python3
# TODO: Add read count statistics
# TODO: Look into BAM statistics

import os
from datetime import datetime
from subprocess import Popen
from shutil import rmtree
import subprocess
from prompt_toolkit import print_formatted_text, HTML
from prompt_toolkit.shortcuts import yes_no_dialog
try:
    from config import COMPANY, ANALYSIS_DIR, RAW_FILES_DIR, NEG_FILE, MATURE_FILE, HP_FILE, CONDITION_FILE, \
    PREFIX, TORONTO_ADAPTERS, BC_ADAPTERS
except ImportError:
    print('ERROR importing config.py file. Check to make sure format is correct')
    exit(1)


class WrongFileTypeError(Exception):
    pass


LOG_FILE = os.path.join(ANALYSIS_DIR, datetime.now().strftime('%d-%m-%y_%H:%M') + '.log')
PIPELINE = 'MicroRNA-seq pypipeline'
FASTQC_DIR = os.path.join(ANALYSIS_DIR, 'fastqc/')
TRIMMED_DIR = os.path.join(ANALYSIS_DIR, 'trimmed/')
ADAPTER_DIR = os.path.join(ANALYSIS_DIR, 'adapters/')
BOWTIE_DIR = os.path.join('/home/student/Desktop/pypipeline', 'bowtie_index/')
NEG_IND_DIR = os.path.join(BOWTIE_DIR, 'neg_ref')
HP_IND_DIR = os.path.join(BOWTIE_DIR, 'hp_ref')
MATURE_IND_DIR = os.path.join(BOWTIE_DIR, 'mature_ref')
FLT_DIR = os.path.join(ANALYSIS_DIR, 'filtered/')
MATURE_DIR = os.path.join(ANALYSIS_DIR, 'matures/')
MATURE_ALIGNED_DIR = os.path.join(MATURE_DIR, 'aligned/')
MATURE_UNALIGNED_DIR = os.path.join(MATURE_DIR, 'unaligned/')
HP_DIR = os.path.join(ANALYSIS_DIR, 'hairpins/')
HP_ALIGNED_DIR = os.path.join(HP_DIR, 'aligned/')
READ_COUNT_DIR = os.path.join(ANALYSIS_DIR, 'read_counts/')
MATURE_READ_COUNT_DIR = os.path.join(READ_COUNT_DIR, 'mature/')
HAIRPIN_READ_COUNT_DIR = os.path.join(READ_COUNT_DIR, 'hairpin/')
R_DATA_FILE = PREFIX + '.Rdata'
CLUS_HEATMAP_FILE = PREFIX + '_clus_geat_map'
VOLCANO_FILE = PREFIX + '_volcano'
PCA_PDF = PREFIX + '_pca_pdf'
PCA_CSV = PREFIX + '_pca_csv'
# FIRST_FILE_BASENAME
# STRESS_NAME

# FORMATED STRINGS
GOOD = HTML('<green>GOOD</green>')
FILE_ALREADY_EXISTS = HTML('<yellow>FILE ALREADY EXISTS</yellow>')
NOT_BUILT = HTML('<yellow>NOT BUILT</yellow>')
BAD = HTML('<red>BAD</red>')
EXITING = HTML('<red>EXITING</red>')
NONE = HTML('')
F_PIPELINE = HTML('<teal>{}</teal>'.format(PIPELINE))


def run_command(message, command, log_output=False):
    formatted_message = '[{}] '.format(PIPELINE) + message + '... '
    print(formatted_message, end='', flush=True)
    with open(LOG_FILE, 'a') as f:
        f.write(formatted_message)

    try:
        if log_output:
            subprocess.call(command + ' >> {}'.format(LOG_FILE), shell=True, stderr=subprocess.STDOUT, stdout=subprocess.DEVNULL)
        else:
            subprocess.call(command, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        print_formatted_text(BAD)
        print('ERROR:')
        print(exc.output.decode('utf-8'))
        with open(LOG_FILE, 'a') as f:
            f.write(exc.output.decode('utf-8'))
        exit(1)

    print_formatted_text(GOOD)


def log_message(message, command_status=GOOD, **kwargs):
    formatted_message = '[{}] '.format(PIPELINE) + message + '... '
    print_formatted_text(HTML(formatted_message + command_status.value), **kwargs)

    with open(LOG_FILE, 'a') as f:
        f.write(formatted_message + '\n')


def create_log_file():
    message = 'Creating log file {}'.format(os.path.basename(LOG_FILE))
    command = 'touch {}'.format(LOG_FILE)
    run_command(message, command)


def validate_file(file_):
    if not os.path.isfile(file_):
        log_message('{} does not exist'.format(file_), command_status=EXITING)
        exit(1)


def validate_config():
    log_message('Performing config validation', command_status=NONE, end='', flush=True)
    validate_file(NEG_FILE)
    validate_file(MATURE_FILE)
    validate_file(HP_FILE)
    validate_file(CONDITION_FILE)

    if COMPANY.upper() not in ['BC', 'TORONTO']:
        log_message('COMPANY must be "BC" or "TORONTO"', command_status=EXITING)
        exit(1)

    if COMPANY.upper() == 'TORONTO':
        adapters = TORONTO_ADAPTERS
    else:
        adapters = BC_ADAPTERS

    if not os.path.isfile(adapters):
        log_message('{} is missing, exiting'.format(adapters), command_status=EXITING)
        exit(1)

    print_formatted_text(GOOD)

    files = '\n'.join([file for file in sorted(os.listdir(RAW_FILES_DIR)) if file.endswith('.fastq') or file.endswith('.fq')])
    continue_ = yes_no_dialog(title='File check', text='Are these the files you want to process?\n\n' + files)
    if not continue_:
        exit(0)


def check_program(program):
    log_message('Checking that {} is installed'.format(program), command_status=NONE, end='', flush=True)

    try:
        Popen([program], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).communicate()
        print_formatted_text(GOOD)
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            log_message('The program {} was not found'.format(program), command_status=BAD)
            exit()
        else:
            log_message('An unknown error occurred when looking for {}'.format(program), command_status=BAD)
            raise


def fastqc_check(fastq_file):
    os.makedirs(FASTQC_DIR, exist_ok=True)

    if not fastq_file.endswith(('.fastq', '.fq')):
        raise WrongFileTypeError('[{}] {} is not a .fastq file'.format(PIPELINE, fastq_file))

    message = 'Performing fastqc check on {}'.format(os.path.basename(fastq_file))
    command = 'fastqc -q {} -o {}'.format(fastq_file, FASTQC_DIR)
    run_command(message, command)


def get_basename(path):
    return os.path.splitext(os.path.basename(path))[0].split('.')[0]


def index_is_built(ind_prefix, index_name):
    try:
        os.listdir(os.path.dirname(ind_prefix))
    except FileNotFoundError:
        log_message('Checking if {} index is built'.format(index_name), command_status=NOT_BUILT)
        return False

    for filename in os.listdir(ind_prefix):
        if not filename.startswith(os.path.basename(ind_prefix)) or not filename.endswith('.ebwt'):
            log_message('Checking if {} index is built'.format(index_name), command_status=NOT_BUILT)
            return False

    log_message('Checking if {} index is built'.format(index_name))
    return True


def build_index(index_dir, index_name):
    if not index_is_built(index_dir, index_name):
        os.makedirs(index_dir, exist_ok=True)

        message = 'Building negative index'
        command = 'bowtie-build {} {}'.format(NEG_FILE, os.path.join(index_dir, os.path.basename(index_dir)))
        run_command(message, command)


def trim_adapters(fastq_file, adapter_file, trim_6=False):
    os.makedirs(TRIMMED_DIR, exist_ok=True)

    output_file = os.path.join(TRIMMED_DIR, get_basename(fastq_file) + '.trimmed.fastq')
    temp_file = os.path.join(TRIMMED_DIR, 'temp.fastq')
    basename = get_basename(fastq_file)

    message = '{}: Trimming adapters'.format(basename)
    command = 'cutadapt -q 20 -m 10 -j 18 -b file:{0} {1} -o {2}'.format(adapter_file, fastq_file, temp_file)
    if os.path.exists(output_file):
        log_message(message, command_status=FILE_ALREADY_EXISTS)
    else:
        run_command(message, command, log_output=True)

        if trim_6:
            message = '{}: Trimming 6 nucleotides'.format(basename)
            command = 'cutadapt -u 6 -j 18 {0} -o {1}'.format(temp_file, output_file)
            run_command(message, command, log_output=True)
            os.remove(temp_file)
        else:
            os.rename(temp_file, output_file)

    return output_file


def filter_out_neg(trimmed_file):
    os.makedirs(FLT_DIR, exist_ok=True)

    basename = get_basename(trimmed_file)
    negative_index = os.path.join(NEG_IND_DIR, os.path.basename(NEG_IND_DIR))
    output_file = os.path.join(FLT_DIR, basename + '.filtered.fastq')

    message = '{}: Filtering negative RNA species'.format(basename)
    command = 'bowtie -p 18 --quiet -q {} {} --un {}'.format(negative_index, trimmed_file, output_file)
    if os.path.exists(output_file):
        log_message(message, command_status=FILE_ALREADY_EXISTS)
    else:
        run_command(message, command, log_output=True)

    return output_file


def align_mature(filtered_file):
    os.makedirs(MATURE_ALIGNED_DIR, exist_ok=True)
    os.makedirs(MATURE_UNALIGNED_DIR, exist_ok=True)

    basename = get_basename(filtered_file)
    mature_index = os.path.join(MATURE_IND_DIR, os.path.basename(MATURE_IND_DIR))
    aligned_sam = os.path.join(MATURE_ALIGNED_DIR, basename + '_MATURE.aligned.sam')
    aligned_bam = os.path.join(MATURE_ALIGNED_DIR, basename + '_MATURE.aligned.bam')
    unaligned_reads = os.path.join(MATURE_UNALIGNED_DIR, basename + '.unaligned.fastq')

    message = '{}: Aligning to mature index'.format(basename)
    command = 'bowtie -p 18 --quiet -q -l 20 -n 0 -v 2 -a -S --best --strata {} {} --al -S {} --un {}'.format(mature_index, filtered_file, aligned_sam, unaligned_reads)
    if os.path.exists(aligned_sam) and os.path.exists(unaligned_reads):
        log_message(message, command_status=FILE_ALREADY_EXISTS)
    else:
        run_command(message, command, log_output=True)

    message = '{}: Converting SAM to BAM'.format(basename)
    command = 'samtools view -S -b {} > {}'.format(aligned_sam, aligned_bam)
    if os.path.exists(aligned_bam):
        log_message(message, command_status=FILE_ALREADY_EXISTS)
    else:
        run_command(message, command)

    return aligned_bam, unaligned_reads


def align_hairpins(unaligned_reads):
    os.makedirs(HP_ALIGNED_DIR, exist_ok=True)

    basename = get_basename(unaligned_reads)
    hairpin_index = os.path.join(HP_IND_DIR, os.path.basename(HP_IND_DIR))
    aligned_sam = os.path.join(HP_ALIGNED_DIR, basename + '_HAIRPIN.aligned.sam')
    aligned_bam = os.path.join(HP_ALIGNED_DIR, basename + '_HAIRPIN.aligned.bam')

    message = '{}: Aligning to hairpin index'.format(basename)
    command = 'bowtie -p 18 --quiet -q -l 20 -n 0 -v 2 -a -S --best --strata {} {} --al -S {}'.format(hairpin_index, unaligned_reads, aligned_sam)
    if os.path.exists(aligned_sam):
        log_message(message, command_status=FILE_ALREADY_EXISTS)
    else:
        run_command(message, command, log_output=True)

    message = '{}: Converting SAM to BAM'.format(basename)
    command = 'samtools view -S -b {} > {}'.format(aligned_sam, aligned_bam)
    if os.path.exists(aligned_bam):
        log_message(message, command_status=FILE_ALREADY_EXISTS)
    else:
        run_command(message, command)

    return aligned_bam


def get_read_counts(read_count_dir, aligned_bam):
    os.makedirs(read_count_dir, exist_ok=True)

    basename = get_basename(aligned_bam)
    sorted_file_bam = os.path.join(read_count_dir, basename + '.sorted.bam')
    readcount = os.path.join(read_count_dir, basename + '.read_count.txt')

    message = '{}: Sorting BAM'.format(basename)
    command = 'samtools sort -n {} -o {}'.format(aligned_bam, sorted_file_bam)
    if os.path.exists(sorted_file_bam):
        log_message(message, command_status=FILE_ALREADY_EXISTS)
    else:
        run_command(message, command)

    message = '{}: Generating read count file'.format(basename)
    command = "samtools view {sorted_file_bam} | awk '{{print $3}}' | sort | uniq -c | sort -nr > {readcount_file}".format(sorted_file_bam=sorted_file_bam, readcount_file=readcount)
    if os.path.exists(readcount):
        log_message(message, command_status=FILE_ALREADY_EXISTS)
    else:
        run_command(message, command)

    return readcount


def copy_read_counts():
    # TODO:
    pass


def run_r_analysis():
    # TODO:
    pass


if __name__ == '__main__':
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    create_log_file()

    # Validate setup
    check_program('fastqc')
    check_program('fastq-mcf')
    check_program('cutadapt')
    check_program('bowtie-build')
    check_program('bowtie')
    check_program('samtools')
    check_program('Rscript')
    validate_config()

    # Set company specific variables
    if COMPANY == 'BC':
        trim_6 = True
        adapter_file = BC_ADAPTERS
    else:
        trim_6 = False
        adapter_file = TORONTO_ADAPTERS

    build_index(NEG_IND_DIR, 'negative')
    build_index(MATURE_IND_DIR, 'mature')
    build_index(HP_IND_DIR, 'hairpin')

    delete = yes_no_dialog(title='Delete files', text='Do you want to delete intermediate files?')

    fastqc = yes_no_dialog(title='FastQC', text='Do you want to perform FastQC on all files?')
    if fastqc:
        for filename in sorted(os.listdir(RAW_FILES_DIR)):
            fastq_file = os.path.join(RAW_FILES_DIR, filename)
            fastqc_check(fastq_file=fastq_file)

    # Process files one at a time
    for filename in sorted(os.listdir(RAW_FILES_DIR)):
        basename = get_basename(filename)
        if not os.path.isfile(os.path.join(MATURE_READ_COUNT_DIR, basename + '_MATURE.read_count.txt')):
            fastq_file = os.path.join(RAW_FILES_DIR, filename)
            trimmed_file = trim_adapters(fastq_file=fastq_file, adapter_file=adapter_file, trim_6=trim_6)
            filtered_file = filter_out_neg(trimmed_file=trimmed_file)
            mature_aligned_bam, unaligned_reads = align_mature(filtered_file)
            hairpin_aligned_bam = align_hairpins(unaligned_reads)
            mature_readcount = get_read_counts(MATURE_READ_COUNT_DIR, mature_aligned_bam)
            hairpin_readcount = get_read_counts(HAIRPIN_READ_COUNT_DIR, hairpin_aligned_bam)

            if delete:
                log_message('{}: Deleting intermediate files'.format(basename))
                rmtree(FLT_DIR)
                rmtree(MATURE_DIR)
                rmtree(HP_DIR)
                rmtree(TRIMMED_DIR)
                os.remove(os.path.join(MATURE_READ_COUNT_DIR, basename + '_MATURE.sorted.bam'))
                os.remove(os.path.join(HAIRPIN_READ_COUNT_DIR, basename + '_HAIRPIN.sorted.bam'))
                os.remove(LOG_FILE)
