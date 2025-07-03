const categories = JSON.parse($(".container").data("categories").replaceAll(/'/g, '"').replaceAll(/True/g, '"True"'));
console.log(categories);

$(document).ready(function() {
  // Handle clicking on the "Report Mistake" card
  $("#reportMistakeBtn").click(function() {
    $("#addStudyForm").hide();
    $("#reportMistakeForm").show();
    $('html, body').animate({
      scrollTop: $("#reportMistakeForm").offset().top - 20
    }, 500);
  });

  // Handle clicking on the "Add Study" card
  $("#addStudyBtn").click(function() {
    $("#reportMistakeForm").hide();
    $("#addStudyForm").show();
    $('html, body').animate({
      scrollTop: $("#addStudyForm").offset().top - 20
    }, 500);
  });

  // Handle cancel buttons
  $(".cancel-btn").click(function() {
    $(this).closest(".form-section").hide();
    $('html, body').animate({
      scrollTop: 0
    }, 500);
  });
});