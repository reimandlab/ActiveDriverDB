function MIMP_image_from_meta(metadata)
{
    var pos = metadata['Position in motif']
    text = '<li class="mimp-logo"><img src="/static/mimp/logos/' + metadata['PWM'] + '.svg"><div class="mimp-outline ' + metadata['Effect'] + '" style="left:' + ((7 + pos) * 22 + 47) + 'px"></div>'
    return text
}
