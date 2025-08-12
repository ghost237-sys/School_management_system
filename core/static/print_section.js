// print_section.js
// Utility to print a section of the page with styles
function printSection(sectionId, title) {
    var content = document.getElementById(sectionId);
    if (!content) {
        alert('Section not found!');
        return;
    }
    var printWindow = window.open('', '', 'height=600,width=900');
    printWindow.document.write('<html><head><title>' + title + '</title>');
    // Copy stylesheets
    var styles = Array.from(document.querySelectorAll('link[rel=stylesheet], style')).map(node => node.outerHTML).join('');
    printWindow.document.write(styles);
    printWindow.document.write('</head><body>');
    printWindow.document.write(content.innerHTML);
    printWindow.document.write('</body></html>');
    printWindow.document.close();
    setTimeout(function(){ printWindow.print(); printWindow.close(); }, 500);
}
