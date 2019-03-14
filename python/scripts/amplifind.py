import sqlalchemy
from dnascissors.config import cfg
from dnascissors.model import Base
from dnascissors.model import Primer
from dnascissors.model import AmpliconSelection
from dnascissors.model import Guide
from dnascissors.model import Target
from dnascissors.model import Project
import requests
import json
from Bio.Seq import Seq
from Bio.Alphabet import IUPAC

REST_ENSEMBL_URL = "http://rest.ensembl.org"


def get_amplicons(dbsession, geid):
    amplicons = []
    amplicon_selections = dbsession.query(AmpliconSelection)\
                                   .join(AmpliconSelection.guide)\
                                   .join(Guide.target)\
                                   .join(Target.project)\
                                   .filter(Project.geid == geid)\
                                   .all()
    # Should do this as another query with IN [amplicon.in_(Primer.amplicons], but it doesn't seem to work.
    primers = dbsession.query(Primer).all()
    for amplicon_selection in amplicon_selections:
        amplicon = amplicon_selection.amplicon
        aprimers = [p for p in primers if amplicon in p.amplicons]
        for primer in aprimers:
            if primer.strand == 'forward':
                fprimer_seq = primer.sequence
                tstart = primer.end + 1
            elif primer.strand == 'reverse':
                rprimer_seq = primer.sequence
                tend = primer.start - 1
        # Add strand information from guide, will not work of multiple guides!
        strand = '+'
        if amplicon_selection.guide_strand == 'reverse':
            strand = '-'
        acoord = "chr{}\t{}\t{}\t{}\t{}".format(amplicon.chromosome,
                                                amplicon.start,
                                                amplicon.end,
                                                strand,
                                                "{}_chr{}_{}".format(amplicon.genome.assembly, amplicon.chromosome, amplicon.start))

        tcoord = "chr{}\t{}\t{}\t{}\t{}".format(amplicon.chromosome,
                                                tstart,
                                                tend,
                                                strand,
                                                "{}_chr{}_{}".format(amplicon.genome.assembly, amplicon.chromosome, tstart))
        amplicons.append({'gene_id': amplicon_selection.guide.target.gene_id,
                          'fprimer_seq': fprimer_seq,
                          'rprimer_seq': rprimer_seq,
                          'amplicon_coord': acoord,
                          'amplicon_len': amplicon.end-amplicon.start+1,
                          'target_coord': tcoord,
                          'target_len': tend-tstart+1,
                          'target_name': amplicon_selection.guide.target.name})
    return amplicons


def find_primer(sequence, primer_seq):
    primer_seq_ori = primer_seq
    primer_loc = sequence.find(primer_seq)
    if primer_loc == -1:
        primer_seq = str(Seq(primer_seq, IUPAC.unambiguous_dna).reverse_complement())
        primer_loc = sequence.find(primer_seq)
    return primer_loc, primer_seq, primer_seq_ori


def get_primer_pair(sequence, fprimer_seq, rprimer_seq):
    fprimer_loc, fprimer_seq, fprimer_seq_ori = find_primer(sequence, fprimer_seq)
    rprimer_loc, rprimer_seq, rprimer_seq_ori = find_primer(sequence, rprimer_seq)
    return fprimer_loc, fprimer_seq, rprimer_loc, rprimer_seq


def find_amplicon_sequence(ensembl_gene_id, fprimer_seq, rprimer_seq):
    # retrieve gene sequence
    url = "{}/sequence/id/{}?species={}".format(REST_ENSEMBL_URL, ensembl_gene_id, 'homo_sapiens')
    r = requests.get(url, headers={"Content-Type": "application/json"})
    gene = json.loads(r.text)
    sequence = gene['seq']
    text, assembly, chr, start, end, strand = gene['desc'].split(':')
    strand = ('+' if strand == '1' else '-')

    fprimer_loc, fprimer_seq, rprimer_loc, rprimer_seq = get_primer_pair(sequence, fprimer_seq, rprimer_seq)

    if fprimer_loc > rprimer_loc:
        fprimer_loc, fprimer_seq, rprimer_loc, rprimer_seq = get_primer_pair(sequence, rprimer_seq, fprimer_seq)

    amplicon_seq = sequence[fprimer_loc:(rprimer_loc + len(rprimer_seq))]
    amplicon_start = int(start) + fprimer_loc - 1
    amplicon_end = int(start) + (rprimer_loc + len(rprimer_seq) - 1)
    amplicon_desc = "{}:chr{}:{}:{}:{}".format(assembly, chr, amplicon_start, amplicon_end, strand)
    acoord = "chr{}\t{}\t{}\t{}\t{}".format(chr,
                                            amplicon_start,
                                            amplicon_end,
                                            strand,
                                            "{}_chr{}_{}".format(assembly, chr, amplicon_start))

    target_start = int(start) + (fprimer_loc + len(fprimer_seq) - 1)
    target_end = int(start) + rprimer_loc - 1
    tcoord = "chr{}\t{}\t{}\t{}\t{}".format(chr,
                                            target_start,
                                            target_end,
                                            strand,
                                            "{}_chr{}_{}".format(assembly, chr, amplicon_start))
    amplicon = {'gene_id': ensembl_gene_id,
                'fprimer_loc': fprimer_loc,
                'fprimer_seq': fprimer_seq,
                'rprimer_loc': rprimer_loc,
                'rprimer_seq': rprimer_seq,
                'seq': amplicon_seq,
                'start': amplicon_start,
                'end': amplicon_end,
                'desc': amplicon_desc,
                'coord': acoord,
                'target_coord': tcoord}
    return amplicon


def print_amplifind_report(i, amplicon, amplifind):
    print('--- Amplicon #{}'.format(i))
    print('Target name\t{}'.format(amplicon['target_name']))
    print('Ensembl Gene ID\t{}'.format(amplifind['gene_id']))
    print('Forward primer\t{}'.format(amplifind['fprimer_seq']))
    print('Reverse primer\t{}'.format(amplifind['rprimer_seq']))
    print('target coord\t{}'.format(amplifind['target_coord']))
    print('amplicon coord\t{}'.format(amplifind['coord']))
    print('amplicon desc\t{}'.format(amplifind['desc']))
    print('amplicon seq\t{}'.format(amplifind['seq']))
    print('amplicon seq len\t{}'.format(len(amplifind['seq'])))
    if amplifind['fprimer_loc'] == -1 or amplifind['rprimer_loc'] == -1:
        print('>>> Primers not found in Ensembl Gene ID {}!'.format(amplicon['gene_id']))
    if not amplicon['amplicon_len'] == len(amplifind['seq']):
        print('>>> Amplicon length different than the one submitted. [submitted: {}, found: {}]'.format(amplicon['amplicon_len'], len(amplifind['seq'])))
    if not amplicon['fprimer_seq'] == amplifind['fprimer_seq']:
        print('>>> Forward primer sequence different than the one submitted! [submitted: {}, found: {}]'.format(amplicon['fprimer_seq'], amplifind['fprimer_seq']))
    if not amplicon['rprimer_seq'] == amplifind['rprimer_seq']:
        print('>>> Reverse primer sequence different than the one submitted! [submitted: {}, found: {}]'.format(amplicon['rprimer_seq'], amplifind['rprimer_seq']))
    if not amplicon['amplicon_coord'] == amplifind['coord']:
        print('>>> Amplicon coord different than the one submitted! [submitted: {}, found: {}]'.format(amplicon['amplicon_coord'], amplifind['coord']))
    if not amplicon['target_coord'] == amplifind['target_coord']:
        print('>>> Amplicon coord different than the one submitted! [submitted: {}, found: {}]'.format(amplicon['target_coord'], amplifind['target_coord']))
    print('---')


def main():
    import sys
    geid = sys.argv[1]  # add your GEPID on the command line
    i = 0
    print('Project ID\t{}'.format(geid))
    engine = sqlalchemy.create_engine(cfg['DATABASE_URI'])
    Base.metadata.bind = engine
    DBSession = sqlalchemy.orm.sessionmaker(bind=engine)
    dbsession = DBSession()
    for amplicon in get_amplicons(dbsession, geid):
        i += 1
        amplifind = find_amplicon_sequence(amplicon['gene_id'], amplicon['fprimer_seq'], amplicon['rprimer_seq'])
        print_amplifind_report(i, amplicon, amplifind)
    dbsession.close()


if __name__ == '__main__':
    main()
