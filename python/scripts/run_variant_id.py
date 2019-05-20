import os
import sys
import plotly.offline as py
import plotly.graph_objs as go
import pandas as pd
from Bio import pairwise2
from varcode import Variant
from pyensembl import ensembl_grch38   # pyensembl install --release 95 --species homo_sapiens

# Consequence weighting
CONSEQUENCE_WEIGHTING = {
    'AlternateStartCodon': 0.5,
    'ComplexSubstitution': 0.5,
    'ExonLoss': 1,
    'ExonicSpliceSite': 0.5,
    'FivePrimeUTR': 0.1,
    'FrameShiftTruncation': 1,
    'FrameShift': 1,
    'IntronicSpliceSite': 0.1,
    'PrematureStop': 1,
    'Silent': 0,
    'SpliceAcceptor': 0.2,
    'SpliceDonor': 0.2,
    'StartLoss': 0.2,
    'StopLoss': 0.2,
    'Substitution': 0.1,
    'ThreePrimeUTR': 0.1,
    'ComplexFrameShift': 0.8,
    'Complex': 0.5
}

# Output folder name for plots and data
folder_name = 'editid_variantid'
if not os.path.exists(folder_name):
    os.mkdir(folder_name)

# Checking two input/output files from amplicount exist
if (not os.path.exists('amplicount.csv')) or (not os.path.exists('amplicount_config.csv')):
    print('Input files amplicount_config.csv, or amplicount.csv not found, please run amplicount tool first.')
    sys.exit(1)

# Load amplicount files (configuration and variants) into pandas dataframe for analysis and ploting
df_config = pd.read_csv('amplicount_config.csv')
df_variants = pd.read_csv('amplicount.csv')

# Filter out low-frequency variants
df_variants = df_variants[(df_variants['variant_frequency'] > 5)]

# List of variants
variants = df_variants[['amplicon_id', 'sequence']]
variants.drop_duplicates(inplace=True)
variants.reset_index(inplace=True)


# Get variant classification using https://github.com/openvax/varcode and https://github.com/openvax/pyensembl
def get_variant_classification(contig, start, ref, alt, genome=ensembl_grch38):
    try:
        var = Variant(contig=contig, start=start, ref=ref, alt=alt, ensembl=genome)
        top_effect = var.effects().top_priority_effect()
        consequence = top_effect.__class__.__name__
        weight = CONSEQUENCE_WEIGHTING.get(consequence, 0)
    except Exception:
        consequence = 'Unclassified'
        weight = 0
    finally:
        if len(ref) > len(alt):
            return 'Deletion', consequence, weight
        elif len(ref) < len(alt):
            return 'Insertion', consequence, weight
        else:
            return 'Mismatch', consequence, weight

# Pairwise alignment to classify variant
with open(os.path.join(folder_name, 'variantid.out'), 'w') as out:
    for i, variant in variants.iterrows():
        # get reference sequence
        amplicon_id = variant['amplicon_id']
        df_ref_sequence = df_config[(df_config['id'] == amplicon_id)]
        ref_sequence = df_ref_sequence.iloc[0]['amplicon']
        variant_id = 'var{}'.format(i + 1)
        data = []
        top_effect_types = set()
        top_effect_consequences = set()
        top_effect_scores = []
        if variant['sequence'] == ref_sequence:
            type = 'WildType'
            top_effect_types.add(type)
            top_effect_consequences.add(type)
            top_effect_scores.append(0)
            coord = df_config[(df_config['id'] == amplicon_id)].iloc[0]['coord']
            out.write(">{}_{}_{}_{}\n{}\n".format(amplicon_id, variant_id, type, coord, ref_sequence))
        else:
            alignments = pairwise2.align.globalms(ref_sequence, variant['sequence'], 5, -4, -3, -0.1)
            ibase_start = 0
            ibase_stop = 0
            variant_results = []
            for ibase in range(1, len(alignments[0][0])-1):
                chr, ref_start = amplicon_id.split('_')
                contig = chr[3:]
                top_effect_consequence = ''
                top_effect_type = ''
                # looking for mismatch
                if not alignments[0][0][ibase] == alignments[0][1][ibase]:
                    if not alignments[0][0][ibase] == '-' and not alignments[0][1][ibase] == '-':
                        start = int(ref_start)+ibase
                        ref = "{}".format(alignments[0][0][ibase])
                        alt = "{}".format(alignments[0][1][ibase])
                        top_effect_type, top_effect_consequence, score = get_variant_classification(contig, start, ref, alt)
                        variant_results.append('{}\t{}\t{}\t{}\t{}'.format(contig, start, ref, alt, top_effect_consequence))
                        top_effect_types.add(top_effect_type)
                        top_effect_consequences.add(top_effect_consequence)
                        top_effect_scores.append(score)
                # looking for insertion and deletion
                if alignments[0][0][ibase] == '-' or alignments[0][1][ibase] == '-':
                    if not alignments[0][0][ibase-1] == '-' and not alignments[0][1][ibase-1] == '-':
                        ibase_start = ibase - 1
                if ibase_start:
                    if not alignments[0][0][ibase+1] == '-' and not alignments[0][1][ibase+1] == '-':
                        ibase_stop = ibase + 1
                if ibase_start and ibase_stop:
                    start = int(ref_start)+ibase_start
                    ref = "{}".format(alignments[0][0][ibase_start:ibase_stop].replace('-', ''))
                    alt = "{}".format(alignments[0][1][ibase_start:ibase_stop].replace('-', ''))
                    top_effect_type, top_effect_consequence, score = get_variant_classification(contig, start, ref, alt)
                    variant_results.append('{}\t{}\t{}\t{}\t{}'.format(contig, start, ref, alt, top_effect_consequence))
                    top_effect_types.add(top_effect_type)
                    top_effect_consequences.add(top_effect_consequence)
                    top_effect_scores.append(score)
                    ibase_start = 0
                    ibase_stop = 0
        if len(top_effect_consequences) > 1:
            if 'FrameShift' in top_effect_consequences:
                top_effect_consequence = 'ComplexFrameShift'
                score = CONSEQUENCE_WEIGHTING.get(top_effect_consequence, 0)
            else:
                top_effect_consequence = 'Complex'
                score = CONSEQUENCE_WEIGHTING.get(top_effect_consequence, 0)
        else:
            top_effect_consequence = ''.join(top_effect_consequences)
            score = top_effect_scores[0]
        name = '{}_{}'.format(variant_id, ','.join(top_effect_consequences))
        out.write(">{}_{}\n{}\n".format(amplicon_id, name, variant['sequence']))
        out.write(pairwise2.format_alignment(*alignments[0]))
        out.write('CHROM\tPOS\tREF\tALT\tTOP_EFFECT\n')
        out.write('{}\n'.format('\n'.join(variant_results)))
        df_variants.loc[((df_variants['amplicon_id'] == amplicon_id) & (df_variants['sequence'] == variant['sequence'])), 'variant_id'] = variant_id
        df_variants.loc[((df_variants['amplicon_id'] == amplicon_id) & (df_variants['sequence'] == variant['sequence'])), 'variant_type'] = '_'.join(top_effect_types)
        df_variants.loc[((df_variants['amplicon_id'] == amplicon_id) & (df_variants['sequence'] == variant['sequence'])), 'variant_consequence'] = top_effect_consequence
        df_variants.loc[((df_variants['amplicon_id'] == amplicon_id) & (df_variants['sequence'] == variant['sequence'])), 'variant_score'] = score
        out.write('\n')

df_variants.to_csv(os.path.join(folder_name, 'variantid.csv'), index=False)